# 🖐️ HandTracking — Control del Cursor con la Mano

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.8%2B-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-Tasks%20v1.0%2B-00A67E?style=for-the-badge&logo=google&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![Architecture](https://img.shields.io/badge/Arquitectura-3%20Capas-blue?style=for-the-badge)

**Control inteligente y ergonómico del cursor del sistema operativo mediante visión artificial en tiempo real y reconocimiento de gestos.**

[Características](#-características-principales) • [Tabla de Gestos](#-esquema-de-gestos) • [Instalación](#-instalación-y-puesta-en-marcha) • [Arquitectura](#-arquitectura-del-sistema) • [Estructura](#-estructura-del-proyecto)

</div>

---

## 📖 Descripción del Proyecto

**HandTracking** es una aplicación de escritorio desarrollada para el **Trabajo Práctico Integrador (TPI)**. Permite controlar el mouse de la computadora mediante gestos manuales capturados a través de cualquier webcam estándar, eliminando la necesidad de hardware costoso o sensores dedicados.

El sistema fue diseñado priorizando la **estabilidad**, la **ergonomía** y la **baja latencia**, minimizando el efecto de fatiga de brazo (*Gorilla Arm Effect*) gracias al mapeo de zonas activas y al suavizado de movimientos.

---

## ✨ Características Principales

- 🎯 **Rastreo por Centro de Palma:** La posición del cursor se calcula a partir del centro biomecánico de la palma (promedio de 5 articulaciones clave), garantizando que el cursor **no tiemble ni se mueva al hacer clics**.
- 🧹 **Filtro de Suavizado Exponencial (EMA):** Elimina el temblor natural de la mano (*jitter*), logrando un movimiento fluido y preciso del cursor.
- 📐 **Zona Activa Ajustable (Bounding Box):** Permite controlar toda la pantalla con movimientos pequeños y descansados de la mano.
- 🤖 **Drag & Drop Robusto con FSM:** Máquina de Estados Finita con confirmación por frames consecutivos, tolerancia ante pérdida breve de detección y supresión de clics parciales accidentales.
- 💾 **Persistencia de Calibración:** Perfiles de usuario y mapeos de gestos almacenados en base de datos local **SQLite** mediante **SQLAlchemy ORM**.
- 🚀 **Descarga Automática de Modelos:** El modelo de detección de MediaPipe (`hand_landmarker.task`) se descarga e inicializa automáticamente al ejecutar el proyecto por primera vez.

---

## ✋ Esquema de Gestos

| Gesto | Configuración de la Mano | Acción en el Sistema |
| :--- | :--- | :--- |
| 🖐️ **MANO_ABIERTA** | Mano extendida / relajada | **Mover Cursor** (rastreo de palma) |
| 🤏 **PELLIZCO_INDICE** | Juntar punta de Pulgar + Índice | **Clic Izquierdo** |
| 🤏 **PELLIZCO_MEDIO** | Juntar punta de Pulgar + Medio | **Clic Derecho** |
| 🤌 **PELLIZCO_TRIPLE** | Juntar Pulgar + Índice + Medio | **Drag & Drop** (Sostener + Arrastrar + Soltar) |
| ✌️ **DOS_DEDOS** | Índice + Medio levantados juntos | **Scroll Vertical** (arriba / abajo) |

---

## 🏗️ Arquitectura del Sistema

El proyecto implementa una **Arquitectura en 3 Capas** estricta, desacoplada y mantenible:

```
┌──────────────────────────────────────────────────────────┐
│             CAPA DE PRESENTACIÓN (views/)                │
│       Dashboard, Calibración visual, Preview cámara      │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│              CAPA DE NEGOCIO (controller/)               │
│  ├── captura.py    → Video & MediaPipe Tasks             │
│  ├── suavizado.py  → Filtro EMA anti-temblor             │
│  ├── gestos.py     → Detección articular y pellizcos     │
│  ├── acciones.py   → Inyección de eventos OS (pynput)    │
│  └── motor.py      → Orquestador central y FSM de Drag   │
└────────────────────────────┬─────────────────────────────┘
                             │ (Únicamente vía repositorio)
                             ▼
┌──────────────────────────────────────────────────────────┐
│                 CAPA DE DATOS (datos/)                   │
│  ├── conexion.py   → Sesión y Engine SQLite              │
│  ├── modelos.py    → Entidades ORM SQLAlchemy            │
│  └── repositorio.py→ CRUD y Perfiles de Calibración      │
└──────────────────────────────────────────────────────────┘
```

---

## 📁 Estructura del Proyecto

```text
TPI-HandTracking/
├── app.py                   # Punto de entrada principal
├── requirements.txt         # Dependencias del proyecto
├── README.md                # Documentación principal
├── PROYECTO.md              # Enunciado y requerimientos del TPI
│
├── controller/              # Capa de Negocio
│   ├── captura.py           # Captura OpenCV y MediaPipe Tasks v1.0+
│   ├── suavizado.py         # Filtro exponencial (EMA)
│   ├── gestos.py            # Reconocimiento de gestos y centro de palma
│   ├── acciones.py          # Controlador de mouse (pynput)
│   └── motor.py             # Pipeline orquestador y FSM de Drag & Drop
│
├── datos/                   # Capa de Datos
│   ├── conexion.py          # Configuración SQLite y sesión SQLAlchemy
│   ├── modelos.py           # Modelos de PerfilCalibracion y ConfiguracionGesto
│   └── repositorio.py       # Consultas y operaciones de persistencia
│
├── views/                   # Capa de Presentación
│   └── ...                  # Componentes de interfaz de usuario
│
└── models/                  # Modelos de Machine Learning (descarga automática)
    └── hand_landmarker.task
```

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar el Repositorio
```bash
git clone https://github.com/juaquin11/TPI_Grupo10_HandTraking.git
cd TPI_Grupo10_HandTraking
```

### 2. Crear y Activar un Entorno Virtual (Opcional pero recomendado)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Ejecutar la Aplicación
```bash
python app.py
```

> **Nota:** En la primera ejecución, el sistema descargará de forma automática el modelo de MediaPipe (`hand_landmarker.task`) y creará la base de datos local con las configuraciones por defecto.

---

## 🎮 Controles durante la Ejecución

- **Cámara / Preview:** Se abrirá una ventana con el tracking visual de landmarks y el estado en tiempo real (`Gesto`, `Acción`, `Drag FSM`).
- **Detener:** Presiona la tecla **`Q`** con la ventana de la cámara enfocada para cerrar la aplicación de manera segura.

---

## 👥 Equipo de Desarrollo — Grupo 10

Trabajo Práctico Integrador desarrollado para la cátedra de **Soporte**.

---

<div align="center">
Desarrollado con ❤️ y Python por el <b>Grupo 10</b>
</div>