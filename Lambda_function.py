import os, json, uuid
import boto3

# === Config ===
TABLE_NAME = os.getenv("TABLE_NAME", "SolicitudesServicioDocente")
ddb = boto3.resource("dynamodb").Table(TABLE_NAME)

# Orden de slots (incluye Confirmacion al final)
SLOT_ORDER = [
    "NombreContacto",
    "NumCelular",
    "NombreHijo",
    "Edad",
    "Escolaridad",
    "DiasSolicitados",
    "HorasDiariasSolicitadas",
    "JornadaSolicitada",
    "Confirmacion",
]

# ===== Utilidades Lex V2 =====
def slots_dict(event):
    return (event.get("sessionState", {}).get("intent", {}) or {}).get("slots") or {}

def get_slot(event, name):
    v = slots_dict(event).get(name)
    return v and v.get("value", {}).get("interpretedValue")

def set_slot_in_event(event, name, value):
    intent = event["sessionState"]["intent"]
    s = intent.get("slots") or {}
    if value is None:
        s[name] = None
    else:
        s[name] = {"value": {"originalValue": str(value), "interpretedValue": str(value)}}
    intent["slots"] = s

def rc(title, subtitle=None, buttons=None):
    card = {"contentType": "ImageResponseCard",
            "imageResponseCard": {"title": title}}
    if subtitle:
        card["imageResponseCard"]["subtitle"] = subtitle
    if buttons:
        card["imageResponseCard"]["buttons"] = buttons
    return card

def elicit_slot(event, slot_name, text, buttons=None):
    # Asegura que el slot existe (evita "slot to elicit is invalid")
    if slot_name not in slots_dict(event):
        set_slot_in_event(event, slot_name, None)
    return {
        "sessionState": {
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": slot_name},
            "intent": event["sessionState"]["intent"],
        },
        "messages": [{"contentType": "PlainText", "content": text}]
                   + ([rc("Opciones", None, buttons)] if buttons else [])
    }

def delegate(event):
    return {
        "sessionState": {
            "dialogAction": {"type": "Delegate"},
            "intent": event["sessionState"]["intent"],
        }
    }

def close_ok(intent_name, text, extra_msgs=None):
    msgs = [{"contentType": "PlainText", "content": text}]
    if extra_msgs: msgs += extra_msgs
    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {"name": intent_name, "state": "Fulfilled"},
        },
        "messages": msgs,
    }

# ===== Prompts base =====
PROMPT = {
    "NombreContacto": "¿Cuál es tu nombre?",
    "NumCelular": "¿Cuál es tu número de celular?",
    "NombreHijo": "¿Cuál es el nombre de tu hijo?",
    "Edad": "¿Cuántos años tiene tu hijo?",
    "Escolaridad": "¿En qué nivel de escolaridad está tu hijo?",
    "DiasSolicitados": "¿Cuántos días a la semana deseas el servicio? (1 a 5)",
    "HorasDiariasSolicitadas": "¿Cuántas horas por día requieres el servicio? (1 a 4)",
    "JornadaSolicitada": "¿Requieres jornada en la mañana o en la tarde?",
}

# ===== Validadores =====
def validate_NumCelular(event):
    valor = get_slot(event, "NumCelular")
    if not valor or not valor.isdigit() or len(valor) != 10:
        return elicit_slot(
            event,
            "NumCelular",
            "El número ingresado no es válido en Colombia. Debe tener 10 dígitos. "
            "Por favor, ingrésalo nuevamente.",
        )
    return None

def validate_Edad(event):
    valor = get_slot(event, "Edad")
    try:
        n = int(valor)
    except (TypeError, ValueError):
        n = None
    if n is None or n < 2 or n > 12:
        return elicit_slot(
            event,
            "Edad",
            "Este servicio es para educación de edades tempranas (2 a 12 años). "
            "No trabajamos con bebés ni adolescentes. "
            "¿Cuántos años tiene tu hijo?",
        )
    return None

def validate_Escolaridad(event):
    valor = (get_slot(event, "Escolaridad") or "").strip().lower()
    if valor not in {"preescolar", "primaria"}:
        return elicit_slot(
            event,
            "Escolaridad",
            PROMPT["Escolaridad"],
            buttons=[{"text": "Preescolar", "value": "Preescolar"},
                     {"text": "Primaria",   "value": "Primaria"}],
        )
    return None

def validate_DiasSolicitados(event):
    valor = get_slot(event, "DiasSolicitados")
    try:
        n = int(valor)
    except (TypeError, ValueError):
        n = None
    if n is None or n < 1 or n > 5:
        return elicit_slot(
            event,
            "DiasSolicitados",
            "Máximo se disponibilizan 5 días a la semana en horarios hábiles. "
            "¿Cuántos días a la semana deseas el servicio? (1 a 5)",
        )
    return None

def validate_HorasDiariasSolicitadas(event):
    valor = get_slot(event, "HorasDiariasSolicitadas")
    try:
        n = int(valor)
    except (TypeError, ValueError):
        n = None
    if n is None or n < 1 or n > 4:
        return elicit_slot(
            event,
            "HorasDiariasSolicitadas",
            "Por reglas de la empresa no se programa a un niño con más de 4 horas diarias. "
            "¿Cuántas horas por día requieres? (1 a 4)",
        )
    return None

def validate_JornadaSolicitada(event):
    valor = (get_slot(event, "JornadaSolicitada") or "").strip().lower()
    normal = {"mañana": "mañana", "manana": "mañana", "tarde": "tarde"}
    if normal.get(valor) not in {"mañana", "tarde"}:
        return elicit_slot(
            event,
            "JornadaSolicitada",
            PROMPT["JornadaSolicitada"],
            buttons=[{"text": "Mañana", "value": "Mañana"},
                     {"text": "Tarde",  "value": "Tarde"}],
        )
    return None

VALIDATORS = {
    "NumCelular": validate_NumCelular,
    "Edad": validate_Edad,
    "Escolaridad": validate_Escolaridad,
    "DiasSolicitados": validate_DiasSolicitados,
    "HorasDiariasSolicitadas": validate_HorasDiariasSolicitadas,
    "JornadaSolicitada": validate_JornadaSolicitada,
}

# ===== Diálogo en orden =====
def ask_next_missing_or_validate(event):
    s = slots_dict(event)
    for name in SLOT_ORDER:
        if name not in s:
            set_slot_in_event(event, name, None)

    # Recorremos hasta llegar a Confirmacion
    for name in SLOT_ORDER:
        if name == "Confirmacion":
            break
        val = get_slot(event, name)
        if val is None:
            if name in {"Escolaridad", "JornadaSolicitada"}:
                return VALIDATORS[name](event)
            return elicit_slot(event, name, PROMPT[name])
        else:
            if name in VALIDATORS:
                bad = VALIDATORS[name](event)
                if bad:
                    return bad
    return None  # todos los datos listos

def resumen_datos(event):
    nombre = get_slot(event, "NombreContacto") or "-"
    celular = get_slot(event, "NumCelular") or "-"
    hijo = get_slot(event, "NombreHijo") or "-"
    edad = get_slot(event, "Edad") or "-"
    esc = get_slot(event, "Escolaridad") or "-"
    dias = get_slot(event, "DiasSolicitados") or "-"
    horas = get_slot(event, "HorasDiariasSolicitadas") or "-"
    jornada = get_slot(event, "JornadaSolicitada") or "-"
    return (
        f"{nombre}, ¿son correctos estos datos?\n"
        f"• Número de celular: {celular}\n"
        f"• Nombre de tu hijo(a): {hijo}\n"
        f"• Edad: {edad}\n"
        f"• Escolaridad: {esc}\n"
        f"• Días por semana: {dias}\n"
        f"• Horas por día: {horas}\n"
        f"• Jornada: {jornada}\n"
        " -> Confirma para continuar. "
    )

def pedir_confirmacion(event):
    if "Confirmacion" not in slots_dict(event):
        set_slot_in_event(event, "Confirmacion", None)
    return {
        "sessionState": {
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": "Confirmacion"},
            "intent": event["sessionState"]["intent"]
        },
        "messages": [
            {"contentType": "PlainText", "content": resumen_datos(event)},
            rc("¿Deseas confirmar?", "Selecciona una opción:",
               buttons=[{"text": "Sí", "value": "sí"}, {"text": "No", "value": "no"}])
        ]
    }

def guardar(event):
    nombre = get_slot(event, "NombreContacto")
    cel = get_slot(event, "NumCelular")
    hijo = get_slot(event, "NombreHijo")
    edad = get_slot(event, "Edad")
    esc = get_slot(event, "Escolaridad")
    dias = get_slot(event, "DiasSolicitados")
    horas = get_slot(event, "HorasDiariasSolicitadas")
    jornada = get_slot(event, "JornadaSolicitada")

    appt_id = "A-" + uuid.uuid4().hex[:8].upper()
    ddb.put_item(Item={
        "SolicitudPK": f"Contract#{appt_id}",
        "SolicitudSK": f"APPT#{appt_id}",
        "nombreContacto": nombre, "celContacto": cel,
        "nombreHijo": hijo, "edadHijo": edad, "escolaridadHijo": esc,
        "numDiasSemanaContrato": dias, "numHorasDiariasContrato": horas,
        "jornadaPreferidaContrato": jornada
    })

    msg = f"Gracias {nombre}. Tu registro ha sido creado. El ID es {appt_id}. Te contactaremos a la brevedad para coordinar detalles. Que tengas un feliz dia!!!"
    extras = [rc("¿Deseas realizar otra solicitud?", None,
                 buttons=[{"text": "Registrar otra", "value": "registrar otra"}])]
    return close_ok("SolicitudServicio", msg, extras)

def reiniciar(event):
    # Limpia slots y vuelve a pedir el primero
    for n in SLOT_ORDER:
        set_slot_in_event(event, n, None)
    return elicit_slot(event, "NombreContacto",
                       "¡Vamos de nuevo! Para registrar otra solicitud, empecemos. ¿Cuál es tu nombre?")

# ===== Handler =====
def lambda_handler(event, context):
    intent = event["sessionState"]["intent"]["name"]
    inv = event.get("invocationSource")
    user_text = (event.get("inputTranscript") or "").strip().lower()

    if intent != "SolicitudServicio":
        return {"sessionState": {"dialogAction": {"type": "ElicitIntent"}},
                "messages": [{"contentType": "PlainText", "content": "Puedo ayudarte a registrar una solicitud de docente."}]}

    # Atajo global: botón "Registrar otra"
    if user_text == "registrar otra":
        return reiniciar(event)

    if inv == "DialogCodeHook":
        # 1) Completar/validar datos en orden (hasta antes de Confirmacion)
        resp = ask_next_missing_or_validate(event)
        if resp:
            return resp

        # 2) Si falta Confirmacion, pedimos (mensaje único + botones)
        confirm = (get_slot(event, "Confirmacion") or "").strip().lower()
        if not confirm:
            return pedir_confirmacion(event)

        # 3) Si dijo NO, no guardamos
        if confirm in {"no", "n"}:
            # Limpia el slot de confirmación para no quedarse pegado
            set_slot_in_event(event, "Confirmacion", None)
            return {
                "sessionState": {"dialogAction": {"type": "ElicitIntent"},
                                 "intent": event["sessionState"]["intent"]},
                "messages": [{"contentType": "PlainText",
                              "content": "Entendido. Dime qué dato deseas corregir o escribe 'registrar otra' para empezar de nuevo."}]
            }

        # 4) Si dijo SÍ, delegamos a fulfillment (Lex volverá a invocarnos)
        return delegate(event)

    if inv == "FulfillmentCodeHook":
        confirm = (get_slot(event, "Confirmacion") or "").strip().lower()
        if confirm in {"sí", "si", "s"}:
            return guardar(event)
        return close_ok("SolicitudServicio", "No se confirmó el registro. Podemos intentarlo de nuevo cuando quieras.")

    # Fallback (no debería llegar)
    return {"sessionState": {"dialogAction": {"type": "ElicitIntent"}},
            "messages": [{"contentType": "PlainText", "content": "¿En qué puedo ayudarte?"}]}
