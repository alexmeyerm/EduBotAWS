/****************************************************
 * Lex V2 + Polly (voz) — UI estilo widget + Quick Replies
 ****************************************************/

// === CONFIG AWS ===
const REGION = "us-east-1";
const IDENTITY_POOL_ID = "us-east-1:b3975441-68a0-459a-9710-83f35dba2d6f";
const BOT_ID = "HHZJB5PJKE";
const BOT_ALIAS_ID = "YMAJBXYUFM";
const LOCALE_ID = "es_419";
const VOICE_ID = "Mia";

// === DOM ===
const $log   = document.getElementById("log");
const $input = document.getElementById("userInput");
const $send  = document.getElementById("sendBtn");
const $reset = document.getElementById("resetBtn");
const $resultIdBox = document.getElementById("resultIdBox");
const $suggBar = document.getElementById("suggBar");

// Estado UI
let ready = false;

// === AWS SDK v2 ===
AWS.config.region = REGION;
AWS.config.credentials = new AWS.CognitoIdentityCredentials({ IdentityPoolId: IDENTITY_POOL_ID });

const lex   = new AWS.LexRuntimeV2({ region: REGION });
const polly = new AWS.Polly({ region: REGION });

// Sesión Lex
function randomUUID() {
  if (window.crypto && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback manual (en caso de HTTP o navegadores sin crypto)
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

let sessionId = localStorage.getItem("lexSessionId") || randomUUID();
localStorage.setItem("lexSessionId", sessionId);


// === Helpers UI (burbujas y typing) ===
function bubble(text, who="bot"){
  const row = document.createElement("div");
  row.className = `row ${who}`;
  if (who === "bot") {
    row.innerHTML = `<div class="avatar">🤖</div><div class="bubble">${text}</div>`;
  } else {
    row.innerHTML = `<div class="bubble">${text}</div>`;
  }
  $log.appendChild(row);
  $log.scrollTop = $log.scrollHeight;
}
function typingOn(){
  const row = document.createElement("div");
  row.className = "row bot";
  row.id = "typing";
  row.innerHTML = `<div class="avatar">🤖</div><div class="bubble" style="opacity:.75">Escribiendo…</div>`;
  $log.appendChild(row);
  $log.scrollTop = $log.scrollHeight;
}
function typingOff(){ document.getElementById("typing")?.remove(); }

// === Quick replies ===
function clearSuggestions(){
  $suggBar.innerHTML = "";
  $suggBar.style.display = "none";
}
function renderSuggestions(buttons){
  clearSuggestions();
  if (!buttons || !buttons.length) return;
  buttons.forEach(btn => {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.type = "button";
    chip.textContent = btn.text || btn.value || "Opción";
    const value = btn.value || btn.text || chip.textContent;
    chip.addEventListener("click", ()=>{
      $input.value = value;
      $send.click(); // dispara turno con ese valor
    });
    $suggBar.appendChild(chip);
  });
  $suggBar.style.display = "flex";
}

// === ID destacado ===
function extractRegistrationId(text){
  if (!text) return null;
  const m = /(?:\bID\b|\bId\b|\bid\b)\s*(?:es|:)?\s*([A-Z]-[A-Z0-9]{6,12})/.exec(text)
         || /\b[A-Z]-[A-Z0-9]{6,12}\b/.exec(text);
  return m ? (m[1] || m[0]) : null;
}
function showResultId(id){
  if (!id) return;
  $resultIdBox.textContent = id;
  $resultIdBox.style.display = "block";
}
function clearResultId(){
  $resultIdBox.textContent = "";
  $resultIdBox.style.display = "none";
}

// === Init credenciales ===
async function initAws() {
  try {
    bubble("Inicializando…", "bot");
    await new Promise((res, rej) => AWS.config.credentials.get(err => err ? rej(err) : res()));
    ready = true;
    $log.innerHTML = "";
    bubble("👋 ¡Hola! Soy tu asistente docente. ¿En qué puedo ayudarte hoy?", "bot");
  } catch (e) {
    console.error("Fallo inicializando credenciales Cognito:", e);
    bubble("⚠️ No pude inicializar credenciales de AWS (Cognito). Revisa la configuración del Identity Pool/Región.", "bot");
  }
}
initAws();

function ensureCreds(){
  return new Promise((res, rej)=> AWS.config.credentials.refresh(err => err ? rej(err) : res()));
}

// === Lex + Polly ===
async function recognizeTextLex(text){
  const params = { botAliasId: BOT_ALIAS_ID, botId: BOT_ID, localeId: LOCALE_ID, sessionId, text };
  const resp = await lex.recognizeText(params).promise();
  return resp; // devolvemos el objeto completo para extraer botones
}
function extractBotText(resp){
  const msgs = (resp.messages || []);
  // concatenamos posibles textos en orden
  const text = msgs
    .filter(m => m.content)
    .map(m => m.content)
    .join(" ");
  return text || "(No tengo respuesta por ahora.)";
}
function extractButtons(resp){
  // Lex V2: imageResponseCard.buttons
  const buttons = [];
  (resp.messages || []).forEach(m => {
    if (m.imageResponseCard && Array.isArray(m.imageResponseCard.buttons)) {
      m.imageResponseCard.buttons.forEach(b => buttons.push({ text: b.text, value: b.value }));
    }
  });
  return buttons;
}

async function synthesizeAndPlay(text){
  const base = { Text: text, OutputFormat: "mp3", VoiceId: VOICE_ID };
  try{
    const data = await polly.synthesizeSpeech({ ...base, Engine: "neural" }).promise();
    play(data.AudioStream);
  }catch{
    const data = await polly.synthesizeSpeech(base).promise();
    play(data.AudioStream);
  }
}
function play(stream){
  if (!stream) return;
  const url = URL.createObjectURL(new Blob([stream], { type: "audio/mpeg" }));
  const audio = new Audio(url);
  audio.play();
}

// === Turno ===
async function processTurn(text){
  if (!ready) return;
  // al enviar algo, ocultamos sugerencias previas
  clearSuggestions();

  bubble(text, "me");
  typingOn();

  try{
    await ensureCreds();
    const resp = await recognizeTextLex(text);

    typingOff();

    const reply = extractBotText(resp);
    bubble(reply, "bot");

    const rid = extractRegistrationId(reply);
    if (rid) showResultId(rid);

    // Extrae y pinta quick replies si vienen en el response card
    const buttons = extractButtons(resp);
    renderSuggestions(buttons);

    synthesizeAndPlay(reply);
  }catch(e){
    typingOff();
    console.error("Error en turno:", e);
    bubble("⚠️ Error al comunicar con AWS: " + (e.message || e), "bot");
  }
}

// === Eventos ===
$send.addEventListener("click", () => {
  const text = $input.value.trim();
  if(!text) return;
  $input.value = "";
  processTurn(text);
});
$input.addEventListener("keydown", e => { if(e.key === "Enter") $send.click(); });

$reset.addEventListener("click", async () => {
  if (!ready) return;

  // (opcional) cierra sesión anterior en Lex, por si quieres “hard reset”
  try {
    await lex.deleteSession({ botAliasId: BOT_ALIAS_ID, botId: BOT_ID, localeId: LOCALE_ID, sessionId }).promise();
  } catch {}

  AWS.config.credentials.clearCachedId?.();
  localStorage.removeItem("lexSessionId");

  // usar SIEMPRE nuestro helper con fallback
  sessionId = randomUUID();
  localStorage.setItem("lexSessionId", sessionId);

  // Limpia UI y saludo inicial
  $log.innerHTML = "";
  bubble("👋 ¡Hola! Soy tu asistente docente. ¿En qué puedo ayudarte hoy?", "bot");

  clearResultId();
  clearSuggestions();
});


// (opcional) foco inicial
$input.focus();
