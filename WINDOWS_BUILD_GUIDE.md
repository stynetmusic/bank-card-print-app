# Инструкция по компиляции под Windows (для Mac M1 пользователей)

Так как вы используете Mac M1, вы не можете напрямую скомпилировать .exe для Windows. 
Вот несколько вариантов получения готового .exe файла:

## Вариант 1: Использование онлайн-сервисов (самый простой)

### GitHub Actions (бесплатно)
1. Загрузите код на GitHub
2. Создайте файл `.github/workflows/build.yml`:
```yaml
name: Build Windows EXE

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: windows-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install PyQt6 Pillow reportlab pyinstaller
    
    - name: Build EXE
      run: |
        pyinstaller --onefile --windowed --name UF_Print_Cards main.py
    
    - name: Upload artifact
      uses: actions/upload-artifact@v3
      with:
        name: UF_Print_Cards_EXE
        path: dist/UF_Print_Cards.exe
```
3. Запустите workflow вручную или сделайте push
4. Скачайте готовый .exe из раздела Artifacts

## Вариант 2: Виртуальная машина Windows на Mac

### Установка Windows на Mac M1

1. **Parallels Desktop** (платно, но надежно)
   - Скачайте Parallels Desktop для Mac
   - Установите Windows 11 ARM
   - Запустите Windows и следуйте инструкциям ниже

2. **VMware Fusion** (бесплатно для личного использования)
   - Скачайте VMware Fusion Tech Preview
   - Установите Windows 11 ARM
   - Запустите Windows и следуйте инструкциям ниже

3. **UTM** (бесплатно, open-source)
   - Скачайте UTM с https://mac.getutm.app/
   - Создайте новую виртуальную машину Windows 11 ARM
   - Запустите и следуйте инструкциям ниже

### Компиляция внутри виртуальной машины Windows

После установки Windows ARM:

1. Откройте терминал или PowerShell в Windows

2. Установите Python:
```bash
winget install Python.Python.3.11
```

3. Перезагрузите терминал

4. Перейдите в папку с проектом (смонтируйте Mac папку или скопируйте файлы)

5. Установите зависимости:
```bash
pip install PyQt6 Pillow reportlab pyinstaller
```

6. Скомпилируйте .exe:
```bash
pyinstaller --onefile --windowed --name UF_Print_Cards main.py
```

7. Готовый файл будет в папке `dist`

**Примечание**: Windows ARM версия .exe будет работать только на Windows ARM, 
но большинство современных приложений Python работают корректно.

## Вариант 3: Использование Windows в облаке

### Azure DevOps (бесплатные кредиты)
1. Зарегистрируйтесь на https://dev.azure.com/
2. Создайте проект и репозиторий
3. Загрузите код
4. Настройте pipeline для сборки Windows .exe
5. Скачайте готовый артефакт

### Другие облачные сервисы
- AWS EC2 (Windows Server)
- Google Cloud Compute Engine
- DigitalOcean (не поддерживает Windows на базовых тарифах)

## Вариант 4: Доступ к реальному компьютеру с Windows

Если у вас есть доступ к:
- Рабочему компьютеру с Windows
- Ноутбуку друга/коллеги с Windows
- Компьютеру в интернет-кафе

Скопируйте файлы проекта и выполните команды из раздела "Компиляция внутри виртуальной машины Windows".

## Рекомендуемый вариант

Для быстрого результата рекомендую **Вариант 1 (GitHub Actions)** - это бесплатно, 
не требует установки Windows на Mac, и полностью автоматизировано.

## Проверка .exe файла

После получения .exe файла:

1. Проверьте его антивирусом (Windows Defender автоматически)
2. Запустите на тестовом компьютере с Windows
3. Убедитесь, что все функции работают корректно

## Если ничего не подходит

Если ни один вариант не подходит, я могу помочь вам:
- Найти сервис по компиляции Python в .exe
- Настроить удаленную сборку
- Предоставить более детальные инструкции для конкретного варианта
