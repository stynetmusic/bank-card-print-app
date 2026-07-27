# Сборка Windows EXE (минимум: Windows 7 x64)

## Важно

- **Нельзя** собрать рабочий Windows `.exe` на Mac. PyInstaller **не** умеет кросс-компиляцию.
- Редактируйте код на Mac; собирайте только через **GitHub Actions** (ниже) или на реальной Windows / VM **x64**.
- Целевой минимум: **Windows 7 SP1 x64**. Тот же артефакт подходит для Windows 10/11 x64.
- Клиенту нужна вся папка `UF_Print_Cards_App` (exe + `_internal`), а не один файл exe.
- На целевой машине желателен [Visual C++ Redistributable x64](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).

## Зафиксированный стек

| Компонент | Версия | Зачем |
|-----------|--------|--------|
| GitHub runner | `windows-2019` | Старый ABI, ближе к Win7 |
| Python | **3.8.10 x64** | Практичный потолок для Win7 |
| GUI | **PyQt5==5.15.4** | PyQt6 / новый Qt часто ломается на Win7 |
| Bundler | **pyinstaller==4.10** | Без `GetSystemTimePreciseAsFileTime` (Win8+) |
| Прочее | `requirements.txt` | `numpy<1.24`, Pillow, reportlab |

Единственный spec: **`build.spec`** (onedir → `dist/UF_Print_Cards_App/`).

## Вариант 1: GitHub Actions (рекомендуется)

Workflow уже в репозитории: `.github/workflows/build.yml`.

1. Push в `main` / `master` или запустите **Actions → Build Windows 7 x64 EXE → Run workflow**.
2. Дождитесь зелёного прогона.
3. Скачайте артефакт **`UF_Print_Cards_Windows7_x64`**.
4. Распакуйте и отдайте клиенту **всю** папку `UF_Print_Cards_App`.

## Вариант 2: Локальная сборка на Windows x64

Только на **Windows x64** (не ARM-only VM, если клиент на Intel/AMD Win7).

```bat
py -3.8 -m pip install --upgrade "pip<25" "setuptools<70" wheel
py -3.8 -m pip install -r requirements.txt
py -3.8 -m PyInstaller --noconfirm build.spec
```

Результат: `dist\UF_Print_Cards_App\`.

Не используйте `pyinstaller --onefile ...` и не ставьте PyQt6 / Python 3.11+ для Win7-сборки.

## Типичные ошибки на Win7

| Сообщение | Причина |
|-----------|---------|
| `GetSystemTimePreciseAsFileTime` / `KERNEL32.dll` | Слишком новый Python или PyInstaller (>4.10) |
| `DLL load failed … QtWidgets` / «Не найдена указанная процедура» | PyQt6 / несовместимый Qt или смесь PyQt5/6 |
| «Невозможно запустить это приложение на вашем ПК» | Неверный бинарник (не x64, битый архив, сборка не с Windows) |

## Проверка

1. Windows Defender / антивирус.
2. Запуск на **реальном Win7 x64** (или чистой VM), не только на Win11.
3. Проверить загрузку картинок, CMYK, экспорт PDF, сохранение заказа.
