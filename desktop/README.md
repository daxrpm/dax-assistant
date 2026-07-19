# Dax Desktop

Cliente nativo de Dax para Linux, construido con Tauri v2, React 19 y
TypeScript. Se conecta directamente por HTTP/WebSocket al backend Python y no
incluye un sidecar Python. [`../docs/desktop-architecture.md`](../docs/desktop-architecture.md)
es la referencia principal de límites e invariantes.

## Implementación

- Chat completo con conversaciones persistidas, Markdown, eventos del agente,
  confirmaciones y correlación estricta mediante `session_id`.
- Settings 6.0 declarativo y buscable: Voz, Inteligencia, Capacidades, Memoria,
  Canales, Acceso y Sistema. Un test compara el registro con todas las hojas de
  `DaxConfig`.
- HUD de voz separado, tray, `Super+Shift+D` para enfocar Dax y `Ctrl+Space`
  press/release para PTT.
- Orb pseudo-3D en Canvas 2D con esfera, órbitas y partículas. Waves separadas
  para micrófono y TTS reciben RMS, peak y spectrum mediante refs imperativas y
  buffers acotados; los level frames no pasan por React state.
- Paleta oscura azul-negra con surface steps y elevación suave. El frame custom
  de 31 px es el predeterminado; Settings permite cambiar en vivo a decoraciones
  nativas sin alterar el HUD.
- Voz local mediante el micrófono del host del backend y voz remota PTT mediante
  PCM mono de 16 kHz por `/ws/voice`. El TTS remoto se reproduce en los altavoces
  del servidor, no vuelve como audio al cliente.
- Texto Kokoro sincronizado por frase en el command deck y el HUD. El evento se
  emite después de sintetizar y justo antes de reproducir audio.
- Card MPRIS con espectro PipeWire de 40 bandas, artwork validado y ducking
  configurable por dispositivo; restaura exactamente el volumen original.
- Métricas nativas de CPU, memoria, uptime y discos; control allowlisted de
  `dax-assistant.service` con `systemctl --user`.
- Autostart y notificaciones nativas configurables. La notificación de
  desconexión se emite después de tres health checks fallidos.
- Interfaz ES/EN, preferencia persistida, layout responsive a 900/720 px,
  pantallas pesadas en lazy chunks y stores WebSocket compartidos por demanda.
- URLs remotas únicamente por HTTPS/WSS; HTTP/WS sólo se admite para loopback.
  Los tokens se guardan por origen en el keyring del SO.

## Primera ejecución y conexión

El onboarding nativo se completa antes de autenticar. Explica privacidad,
permite elegir `local`, `remote` o `hybrid`, valida las URLs y comprueba la
conectividad. Detectar `dax-assistant.service` no implica iniciarlo: la app pide
consentimiento explícito antes de ejecutar el `systemctl --user start`
allowlisted.

La configuración nativa usa el esquema v2; el documento v1 `{mode,url}` se
migra al leerlo y se reescribe de forma atómica. En `hybrid`, remoto se intenta
primero y sólo se hace fallback a loopback tras tres fallos confirmados. No hay
failback automático durante una sesión activa. Cambiar de origen cierra los
stores realtime y carga únicamente el token de ese origen. Desktop Settings y
la pantalla de backend inaccesible permiten reconfigurar la estrategia después
del onboarding.

## Requisitos

Fedora 44:

```bash
sudo dnf install webkit2gtk4.1-devel openssl-devel curl wget file \
  libappindicator-gtk3-devel librsvg2-devel libxdo-devel gcc gcc-c++ make
```

También se requieren Rust stable y Node 22 LTS para compilar. El backend se
instala y opera por separado según el `README.md` raíz.

## Desarrollo

```bash
cd desktop
npm install
npm run tauri dev
```

El backend añade automáticamente `tauri://localhost` y
`http://tauri.localhost` a CORS. No hay que editar `web.cors_origins` para la app
empaquetada. En desarrollo, Vite usa `http://localhost:5273`; si se ejecuta la UI
contra un backend separado, añada ese origen a la configuración de desarrollo.

Un `cargo build` normal no embebe `dist/`: el binario debug espera el `devUrl` y
muestra una ventana vacía si Vite no está ejecutándose. Use `npm run tauri dev`
o `npm run tauri build`.

## Verificación reproducible

Desde la raíz del repositorio:

```bash
~/.local/bin/uv run pytest -q
~/.local/bin/uv run ruff check src tests
~/.local/bin/uv run mypy src

cd desktop
npm run typecheck
npm test
npm run build
npm audit --omit=dev

cd src-tauri
cargo fmt --all -- --check
cargo test --all-targets --all-features
cargo clippy --all-targets --all-features -- -D warnings
```

Última ejecución registrada, 2026-07-19: 316 tests backend, 61 frontend y 26
Rust; `npm audit --omit=dev` informó 0 vulnerabilidades, y build, ruff, mypy y
clippy quedaron limpios.

## Paquetes

```bash
cd desktop
npm run tauri build
# o sólo uno:
npm run tauri build -- --bundles rpm
npm run tauri build -- --bundles deb
```

Targets soportados: RPM y deb. No se configura AppImage ni Flatpak. La build del
2026-07-19 produjo:

| Artefacto | Tamaño exacto |
| --- | ---: |
| `src-tauri/target/release/dax-desktop` | 7,363,440 bytes |
| `bundle/rpm/Dax-0.1.0-1.x86_64.rpm` | 3,426,926 bytes |
| `bundle/deb/Dax_0.1.0_amd64.deb` | 3,425,614 bytes |

Estos artefactos se compilaron correctamente, pero no consta una instalación en
un Fedora limpio.

## Límites verificados

- GNOME/Wayland crea el HUD transparente y always-on-top, pero puede ignorar su
  posición y tamaño solicitados. El compositor decide la colocación; el clipping
  visual de sombras aún requiere inspección humana.
- Las pruebas automatizadas no sustituyen una revisión visual humana, una prueba
  real de micrófono/altavoces/PTT/wake word ni una comprobación completa de
  teclado y accesibilidad.
- Siguen pendientes la validación de audio y visualización con hardware, la
  revisión visual completa, Wayland interactivo, PTT remoto entre dos hosts y
  la instalación/desinstalación en un sistema limpio.
- El modo sidecar no se distribuye. La app controla el servicio de usuario local
  o se conecta a un backend remoto HTTPS.

`PLAN.md` conserva las decisiones cerradas y el registro detallado de hitos;
`docs/desktop-architecture.md` es la referencia arquitectónica principal.
