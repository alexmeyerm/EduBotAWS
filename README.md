
# 🤖 EduBotAWS  
### Asistente Virtual para Registro de Solicitudes Docentes  
*(Virtual Assistant for Teacher Request Registration)*  

---

## 🌍 Descripción General | Overview  

**EduBotAWS** es un asistente virtual inteligente desarrollado con servicios **AWS (Amazon Web Services)** que permite a los usuarios registrar solicitudes docentes para programas de educación temprana de manera natural y guiada.  

El asistente conversa en **español (LATAM)**, valida los datos ingresados, genera un **ID único de solicitud** y confirma el registro.  
Su diseño combina tecnologías **serverless**, **inteligencia conversacional (Lex V2)** y una interfaz web moderna hospedada en **Amazon S3**.

**Live URL:**  
👉 [http://solicituddocente.s3-website-us-east-1.amazonaws.com/](http://solicituddocente.s3-website-us-east-1.amazonaws.com/)

---

## 🧩 Arquitectura | Architecture  

### Diagrama General  
```plaintext
Usuario → Sitio Web (S3) → Amazon Cognito → Amazon Lex V2 → AWS Lambda → DynamoDB / Polly
```

### Componentes Principales  
| Servicio AWS | Función | Descripción |
|---------------|----------|--------------|
| **Amazon Lex V2** | NLU / NLG | Reconoce el lenguaje natural, administra intents y slots. |
| **AWS Lambda** | Backend serverless | Ejecuta validaciones, genera IDs y guarda datos. |
| **Amazon DynamoDB** | Base de datos NoSQL | Almacena las solicitudes registradas. |
| **Amazon Polly** | Texto a Voz | Convierte respuestas a voz (voz *Lucia* en español LATAM). |
| **Amazon Cognito** | Autenticación | Permite el acceso seguro al bot desde la web. |
| **Amazon S3** | Frontend Web | Hospeda los archivos `index.html` y `webapp.js`. |
| **Amazon CloudWatch** | Observabilidad | Logs, monitoreo y trazabilidad de Lambda y Lex. |

---

## 💬 Intents y Slots  
### Intents  
1. **SaludoIntent** – Reconoce saludos comunes (“hola”, “buenos días”).  
2. **SolicitudServicioIntent** – Registra la solicitud del docente con todos los datos requeridos.  
3. **FallbackIntent** – Maneja entradas no comprendidas.  

### Slots Principales  
| Nombre | Tipo | Descripción |
|--------|------|-------------|
| `nombreContacto` | Text | Nombre del solicitante. |
| `celContacto` | Número | Teléfono validado (10 dígitos). |
| `nombreHijo` | Text | Nombre del menor. |
| `edadHijo` | Number | Edad entre 2 y 12 años. |
| `escolaridadHijo` | Enum | Opciones: Preescolar / Primaria. |
| `diasPorSemana` | Number | Días solicitados (1–5). |
| `horasPorDia` | Number | Horas diarias (1–4). |
| `jornadaPreferidaContrato` | Enum | Mañana / Tarde. |
| `confirmacion` | Boolean | Sí / No. |

---

## ⚙️ Lógica de la Lambda  
**Nombre:** `lambda_SolicitudDocente`  
**Lenguaje:** Python 3.12  

**Funciones principales:**
- Validar datos (edad, celular, días y horas).
- Crear un ID único (por ejemplo `A-754A032A`).
- Guardar el registro en **DynamoDB**.
- Enviar mensaje de confirmación con *response cards* (botones).

**Pseudocódigo Simplificado**
```python
if event["invocationSource"] == "DialogCodeHook":
    validar_slots()
elif event["invocationSource"] == "FulfillmentCodeHook":
    guardar_en_dynamodb()
    return close("Tu solicitud fue registrada correctamente.")
```

---

## 🔊 Voz Seleccionada (Amazon Polly)  
- **Voz:** *Lucia (es-LA)*  
- **Motivo:** tono cálido, fluido y natural.  
- **Beneficio:** mejora la accesibilidad y genera empatía con el usuario.

---

## 🔐 Seguridad  
El proyecto implementa un **Amazon Cognito Identity Pool** con credenciales temporales para usuarios no autenticados.  
El rol asociado (inline policy) otorga permisos mínimos para:
- `lex:RecognizeText`
- `lex:GetSession`
- `lex:PutSession`
- `polly:SynthesizeSpeech`

---

## 🌐 Hosting del Sitio Web  
- **Servicio:** Amazon S3 (Static Website Hosting).  
- **Archivos principales:**  
  - `index.html` → interfaz base del chat.  
  - `webapp.js` → lógica de integración con Lex y Polly.  
- **CORS habilitado** para el runtime de Lex.  

---

## 📊 Base de Datos (DynamoDB)  
**Tabla:** `SolicitudesServicioDocente`  
**Claves:**  
- `SolicitudPK` = `Contract#<ID>`  
- `SolicitudSK` = `APPT#<ID>`  

**Atributos:**  
`nombreContacto`, `celContacto`, `nombreHijo`, `edadHijo`, `escolaridadHijo`, `diasPorSemana`, `horasPorDia`, `jornadaPreferidaContrato`, `createdAt`.

---

## 🚀 Despliegue  

### Prerrequisitos  
- AWS CLI configurado  
- Permisos IAM (Lambda, Lex, DynamoDB, S3, Polly, Cognito)

### Pasos  
1. Crear bucket S3 y subir `index.html` y `webapp.js`.  
2. Configurar hosting estático.  
3. Crear el bot en Lex con intents y slots.  
4. Crear Lambda (`lambda_SolicitudDocente`) y vincular al alias del bot.  
5. Crear tabla DynamoDB.  
6. Crear Identity Pool en Cognito con políticas de acceso.  
7. Probar el flujo y habilitar logs en CloudWatch.

---

## 📁 Repositorio  
**GitHub:** [https://github.com/alexmeyerm/EduBotAWS](https://github.com/alexmeyerm/EduBotAWS)  
**Fecha:** Octubre 2025  

---

