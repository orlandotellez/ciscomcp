# PASOS PARA ACTIVAR Y VER LOGS DEL MCP BRIDGE EN CISCO PACKET TRACER

## ¿Por qué antes no abría ninguna ventana ni salían logs en Debug?
1. **`main.js` usaba una función inexistente (`gui.createHtmlWindow`)**: En Cisco Packet Tracer 8.x, las ventanas HTML de un Script Module se abren con **`webViewManager.createWebView("...", "this-sm:bridge.html", 600, 450)`** y **`bridgeWebView.show()`**.
2. **`main.js` no llamaba a `dprint(...)` y tenía `catch (e) {}` vacíos**: En Packet Tracer, el botón **Debug** solo muestra lo que se imprime con `dprint("...")`. Al estar vacío, no mostraba nada.
3. **Los métodos IPC de `bridge.html` tenían nombres antiguos/incorrectos**: Se corrigieron a la API real de Packet Tracer 8.1 (`getDeviceCount()`, `getDeviceAt(i)`, `LogicalWorkspace.addDevice(...)`, `LogicalWorkspace.createLink(...)` con `CONNECT_TYPES = 8100+`, etc.) ejecutados desde el **Script Engine (`main.js`)** vía `$seev()`.

---

## Paso a paso en Cisco Packet Tracer (Solo se hace 1 vez)

1. En Cisco Packet Tracer, ve al menú superior:
   **Extensions > Scripting > Configure PT Script Modules...**
2. Selecciona tu módulo en la lista y haz clic en **Edit** (o si no tienes uno, ve a **Extensions > Scripting > New PT Script Module**).
3. **Pestaña `General` (¡MUY IMPORTANTE para que funcionen los comandos!):**
   - En **Security Privileges**, asegúrate de marcar **todos los permisos** (especialmente *Network*, *Logical Workspace*, *Application Window*, *Misc GUI*, etc.). Si no tienen check, Packet Tracer bloquea las llamadas IPC.
4. **Pestaña `Script Engine`:**
   - Selecciona el archivo `main.js` (o `bridge.js`) que tengas en la lista de la izquierda.
   - En el editor de código de la derecha, borra lo que tenga y pon **esta única línea** (así Packet Tracer siempre leerá el archivo actualizado del disco sin tener que copiar y pegar nunca más):
     ```javascript
     #include "/home/kenerth/IA redes/pt_bridge/main.js"
     ```
     *(O bien, haz clic en **Import**, selecciona `/home/kenerth/IA redes/pt_bridge/main.js` o copia/pega el contenido de `pt_bridge/main.js`)*.
5. **Pestaña `Custom Interfaces`:**
   - Verifica que en la lista de la izquierda exista un archivo llamado exactamente **`bridge.html`**.
   - Si no existe, haz clic en **Add** (nombre: `bridge.html`) o **Import** y selecciona `/home/kenerth/IA redes/pt_bridge/bridge.html`.
   - En el editor de la derecha de `bridge.html`, puedes poner esta única línea para que siempre cargue desde disco:
     ```html
     #include "/home/kenerth/IA redes/pt_bridge/bridge.html"
     ```
     *(O bien importa directamente `/home/kenerth/IA redes/pt_bridge/bridge.html`)*.
6. **Probar y ver los Logs en tiempo real:**
   - En la pestaña **Script Engine**, haz clic primero en el botón **Debug** (se abrirá la ventana *Debug* de Packet Tracer).
   - Ahora haz clic en **Start** (o si decía *Stop*, dale a **Stop** y luego a **Start**).
   - Si te pregunta si deseas resolver/expandir los `#include`, elige **No** mientras desarrollas (o **Yes** si quieres incrustarlos en el `.pts`).
   - **Verás inmediatamente:**
     1. En la ventana **Debug** de Packet Tracer:
        ```text
        [HH:MM:SS] [MCP-SE] ==================================================
        [HH:MM:SS] [MCP-SE] Iniciando MCP Bridge Script Module (main)...
        [HH:MM:SS] [MCP-SE] Acceso IPC verificado correctamente. Dispositivos actuales en topología: 0
        [HH:MM:SS] [MCP-SE] Ventana 'MCP Bridge' abierta correctamente (this-sm:bridge.html).
        ```
     2. Se abrirá automáticamente la ventana oscura **"MCP Bridge - Packet Tracer (Logs & Estado)"** con el indicador en verde **"Conectado a MCP Server"** y un botón **"Probar IPC"**.
     3. En tu terminal o archivo `/home/kenerth/IA redes/mcp_server.log` verás todos los logs tanto del servidor Python como del Bridge dentro de Packet Tracer:
        ```bash
        tail -f "/home/kenerth/IA redes/mcp_server.log"
        ```
7. Finalmente, haz clic en **Save** dentro de la ventana de edición del Script Module para que quede guardado.
