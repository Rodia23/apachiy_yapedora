# 🤖 Yape Auto-Scraper (ADB + OCR)

Un bot RPA local para extraer datos de transferencias de Yape directamente desde un celular físico conectado por USB, evadiendo las restricciones de seguridad (`FLAG_SECURE`) mediante la descarga de comprobantes y reconocimiento óptico de caracteres (OCR).

## 🚀 Requisitos
- Dispositivo Android con Depuración USB activada.
- [Herramientas de plataforma Android (ADB)](https://developer.android.com/studio/releases/platform-tools) en el PATH de Windows.
- Python 3.x
- Motor [Tesseract-OCR](https://github.com/UB-Mannheim/tesseract/wiki) instalado en el sistema.

## 📦 Instalación
1. Clonar el repositorio.
2. Instalar dependencias: `pip install pytesseract Pillow`
3. Conectar el celular y verificar conexión con `adb devices`.

## ⚙️ Uso
Modifica las coordenadas `(X, Y)` en el archivo principal según la resolución de tu dispositivo. Ejecuta el script:
`python scraper_yape.py`
Los resultados se guardarán automáticamente en `registro_yapeos.csv`.