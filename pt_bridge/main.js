// ============================================================================
// MCP Bridge - Script Engine (main.js) para Cisco Packet Tracer 8.x
// ============================================================================
// Este archivo corre en el Script Engine de Packet Tracer.
// Usa dprint() para mostrar logs detallados en el botón "Debug" de PT,
// y webViewManager.createWebView() para abrir la ventana visual del Bridge.
// ============================================================================

var bridgeWebView = null;

function logDebug(msg) {
    var ts = new Date().toLocaleTimeString();
    var line = "[" + ts + "] [MCP-SE] " + msg;
    try {
        if (typeof dprint === "function") {
            dprint(line);
        }
    } catch (e) {}
    return line;
}

function getLogicalWorkspace() {
    return ipc.appWindow().getActiveWorkspace().getLogicalWorkspace();
}

function resolveDeviceType(deviceType) {
    if (typeof deviceType === "number") {
        return deviceType;
    }
    var key = String(deviceType || "").toLowerCase().trim();
    var map = {
        "router": 0,
        "erouter": 0,
        "switch": 1,
        "eswitch": 1,
        "cloud": 2,
        "bridge": 3,
        "hub": 4,
        "repeater": 5,
        "accesspoint": 7,
        "ap": 7,
        "pc": 8,
        "epc": 8,
        "server": 9,
        "eserver": 9,
        "printer": 10,
        "wirelessrouter": 11,
        "ipphone": 12,
        "dslmodem": 13,
        "cablemodem": 14,
        "multilayerswitch": 16,
        "l3switch": 16,
        "switch3650": 17,
        "laptop": 18,
        "tablet": 19,
        "tabletpc": 19,
        "pda": 20,
        "wirelessenddevice": 21,
        "wiredenddevice": 22,
        "tv": 23,
        "asa": 27,
        "firewall": 27,
        "ioe": 28,
        "iot": 28,
        "homegateway": 29,
        "celltower": 31,
        "sniffer": 35,
        "mcu": 36,
        "sbc": 37,
        "thing": 38,
        "wlc": 41
    };
    if (map.hasOwnProperty(key)) {
        return map[key];
    }
    var parsed = parseInt(key, 10);
    return isNaN(parsed) ? 0 : parsed;
}

function resolveCableType(cableType) {
    if (typeof cableType === "number") {
        return cableType >= 8100 ? cableType : (8100 + cableType);
    }
    var key = String(cableType || "straight").toLowerCase().trim();
    // En Packet Tracer 8.x: CONNECT_TYPES empieza en 8100
    var map = {
        "straight": 8100,
        "ethernet_straight": 8100,
        "copper_straight": 8100,
        "cross": 8101,
        "crossover": 8101,
        "ethernet_cross": 8101,
        "roll": 8102,
        "rollover": 8102,
        "fiber": 8103,
        "phone": 8104,
        "cable": 8105,
        "serial": 8106,
        "dce": 8106,
        "dte": 8106,
        "auto": 8107,
        "console": 8108,
        "wireless": 8109,
        "coaxial": 8110,
        "octal": 8111,
        "cellular": 8112,
        "usb": 8113,
        "custom_io": 8114
    };
    return map.hasOwnProperty(key) ? map[key] : 8107;
}

// Función global invocada desde bridge.html vía $seev()
function executeMcpCommand(rawJson) {
    logDebug("Recibido comando desde WebView: " + rawJson);
    var req = null;
    try {
        req = (typeof rawJson === "string") ? JSON.parse(rawJson) : rawJson;
    } catch (e) {
        var parseErr = "JSON inválido en executeMcpCommand: " + e;
        logDebug("ERROR: " + parseErr);
        return JSON.stringify({ id: null, success: false, data: null, error: parseErr });
    }

    var id = req.id;
    var action = req.action;
    var params = req.params || {};
    var response = { id: id, success: false, data: null, error: null };

    try {
        var net = ipc.network();
        if (!net) {
            throw new Error("ipc.network() devolvió null. Verifica los permisos (Security Privileges) del Script Module.");
        }

        if (action === "ping") {
            var count = net.getDeviceCount();
            response.success = true;
            response.data = { status: "ok", device_count: count };
            logDebug("Ping OK - Dispositivos en red: " + count);
        }
        else if (action === "list_devices") {
            var devCount = net.getDeviceCount();
            var devices = [];
            for (var i = 0; i < devCount; i++) {
                var dev = net.getDeviceAt(i);
                if (dev) {
                    devices.push({
                        name: dev.getName(),
                        model: dev.getModel(),
                        type: dev.getType(),
                        x: dev.getXCoordinate(),
                        y: dev.getYCoordinate(),
                        power: dev.getPower()
                    });
                }
            }
            response.success = true;
            response.data = devices;
            logDebug("list_devices OK -> " + devices.length + " dispositivos encontrados.");
        }
        else if (action === "add_device") {
            var lw = getLogicalWorkspace();
            var typeId = resolveDeviceType(params.device_type);
            var model = String(params.model || "2911");
            var desiredName = params.name ? String(params.name) : "";
            var x = Number(params.x || 100);
            var y = Number(params.y || 100);

            logDebug("Añadiendo dispositivo: type=" + typeId + " (" + params.device_type + "), model=" + model + ", name=" + desiredName + ", x=" + x + ", y=" + y);
            var createdName = lw.addDevice(typeId, model, x, y);
            if (!createdName) {
                throw new Error("LogicalWorkspace.addDevice falló para type=" + typeId + ", model=" + model);
            }
            var finalName = createdName;
            var addedDev = net.getDevice(createdName);
            if (addedDev) {
                try {
                    if (typeof addedDev.skipBoot === "function") {
                        addedDev.skipBoot();
                    }
                } catch (eBoot) {}
                if (desiredName && desiredName !== createdName) {
                    addedDev.setName(desiredName);
                    finalName = addedDev.getName();
                }
            }
            response.success = true;
            response.data = { created_name: createdName, name: finalName, model: model, type: typeId, x: x, y: y };
            logDebug("add_device OK -> creado='" + createdName + "', nombre final='" + finalName + "'");
        }
        else if (action === "remove_device") {
            var lwRem = getLogicalWorkspace();
            var targetName = String(params.name || "");
            var removed = lwRem.removeDevice(targetName);
            if (!removed) {
                throw new Error("No se pudo eliminar el dispositivo '" + targetName + "' (¿existe?)");
            }
            response.success = true;
            response.data = { name: targetName, removed: true };
            logDebug("remove_device OK -> '" + targetName + "' eliminado.");
        }
        else if (action === "get_device_ports") {
            var devName = String(params.device || "");
            var d = net.getDevice(devName);
            if (!d) {
                throw new Error("Dispositivo no encontrado: " + devName);
            }
            var pCount = d.getPortCount();
            var ports = [];
            for (var p = 0; p < pCount; p++) {
                var portObj = d.getPortAt(p);
                if (portObj) {
                    var info = { name: portObj.getName() };
                    try { info.ip = portObj.getIpAddress(); } catch (e1) {}
                    try { info.mask = portObj.getSubnetMask(); } catch (e2) {}
                    try { info.up = portObj.isPortUp(); } catch (e3) {}
                    ports.push(info);
                }
            }
            response.success = true;
            response.data = ports;
            logDebug("get_device_ports OK -> " + devName + " tiene " + ports.length + " puertos.");
        }
        else if (action === "connect_link") {
            var lwLink = getLogicalWorkspace();
            var dev1 = String(params.dev1 || "");
            var port1 = String(params.port1 || "");
            var dev2 = String(params.dev2 || "");
            var port2 = String(params.port2 || "");
            var cType = resolveCableType(params.cable_type);

            logDebug("Conectando enlace: " + dev1 + ":" + port1 + " <-> " + dev2 + ":" + port2 + " (cable=" + params.cable_type + " -> " + cType + ")");
            var linked = false;
            if (params.cable_type === "auto" && (!port1 || !port2)) {
                lwLink.autoConnectDevices(dev1, dev2);
                linked = true;
            } else {
                linked = lwLink.createLink(dev1, port1, dev2, port2, cType);
            }
            if (!linked) {
                throw new Error("LogicalWorkspace.createLink devolvió false para " + dev1 + ":" + port1 + " <-> " + dev2 + ":" + port2);
            }
            response.success = true;
            response.data = { connected: true, dev1: dev1, port1: port1, dev2: dev2, port2: port2, cable_type: cType };
            logDebug("connect_link OK");
        }
        else if (action === "configure_ios") {
            var iosDevName = String(params.device || "");
            var commands = params.commands || [];
            var iosDev = net.getDevice(iosDevName);
            if (!iosDev) {
                throw new Error("Dispositivo no encontrado: " + iosDevName);
            }
            try {
                if (typeof iosDev.isBooting === "function" && iosDev.isBooting()) {
                    logDebug("Dispositivo " + iosDevName + " aún arrancando; ejecutando skipBoot()...");
                    iosDev.skipBoot();
                } else if (typeof iosDev.skipBoot === "function") {
                    iosDev.skipBoot();
                }
            } catch (eBoot) {}
            var cli = iosDev.getCommandLine();
            if (!cli) {
                throw new Error("El dispositivo '" + iosDevName + "' no tiene CLI IOS disponible (getCommandLine() == null).");
            }

            // Salir de diálogo inicial si aplica y entrar a modo privilegiado
            try { cli.enterCommand("no"); } catch (e0) {}
            try { cli.enterCommand(""); } catch (e1) {}
            try { cli.enterCommand("enable"); } catch (e2) {}

            for (var c = 0; c < commands.length; c++) {
                var cmd = String(commands[c]);
                cli.enterCommand(cmd);
                logDebug("IOS [" + iosDevName + "]> " + cmd);
            }
            var promptNow = "";
            try { promptNow = cli.getPrompt(); } catch (ep) {}
            response.success = true;
            response.data = { device: iosDevName, executed: commands.length, prompt: promptNow };
            logDebug("configure_ios OK en " + iosDevName + " (" + commands.length + " comandos).");
        }
        else if (action === "configure_pc_ip") {
            var pcName = String(params.device || "");
            var ip = String(params.ip || "");
            var mask = String(params.subnet_mask || "255.255.255.0");
            var gw = String(params.gateway || "0.0.0.0");
            var dhcp = Boolean(params.dhcp);
            var portName = String(params.port || "FastEthernet0");

            var pcDev = net.getDevice(pcName);
            if (!pcDev) {
                throw new Error("Dispositivo no encontrado: " + pcName);
            }
            var hostPort = pcDev.getPort(portName);
            if (!hostPort && pcDev.getPortCount() > 0) {
                hostPort = pcDev.getPortAt(0);
            }
            if (!hostPort) {
                throw new Error("No se encontró puerto de red en " + pcName);
            }

            if (dhcp) {
                hostPort.setDhcpClientFlag(true);
                logDebug("PC [" + pcName + "] DHCP activado en " + hostPort.getName());
            } else {
                try { hostPort.setDhcpClientFlag(false); } catch (ed) {}
                hostPort.setIpSubnetMask(ip, mask);
                if (gw && gw !== "0.0.0.0") {
                    try { hostPort.setDefaultGateway(gw); } catch (eg) {}
                }
                logDebug("PC [" + pcName + "] IP estática configurada: " + ip + " / " + mask + " GW " + gw);
            }

            response.success = true;
            response.data = {
                device: pcName,
                port: hostPort.getName(),
                dhcp: dhcp,
                ip: hostPort.getIpAddress(),
                subnet_mask: hostPort.getSubnetMask()
            };
        }
        else {
            throw new Error("Acción desconocida: " + action);
        }
    } catch (err) {
        var msg = (err && err.message) ? err.message : String(err);
        response.success = false;
        response.error = msg;
        logDebug("ERROR ejecutando '" + action + "': " + msg);
    }

    return JSON.stringify(response);
}

function openBridgeWindow() {
    logDebug("Intentando abrir ventana WebView del MCP Bridge...");
    try {
        if (typeof webViewManager === "undefined" || !webViewManager) {
            logDebug("ERROR CRÍTICO: 'webViewManager' no existe en este contexto.");
            return false;
        }
        if (bridgeWebView) {
            try {
                webViewManager.closeWebView(bridgeWebView.getWebViewId());
            } catch (eClose) {}
            bridgeWebView = null;
        }
        // En PT Script Modules, los archivos en Custom Interfaces se referencian con this-sm:<nombre>
        bridgeWebView = webViewManager.createWebView(
            "MCP Bridge - Packet Tracer (Logs & Estado)",
            "this-sm:bridge.html",
            600,
            450
        );
        if (!bridgeWebView) {
            logDebug("ERROR: webViewManager.createWebView devolvió null. ¿Existe 'bridge.html' en la pestaña Custom Interfaces?");
            return false;
        }
        bridgeWebView.show();
        logDebug("Ventana 'MCP Bridge' abierta correctamente (this-sm:bridge.html).");
        return true;
    } catch (e) {
        logDebug("EXCEPCIÓN al abrir WebView: " + ((e && e.message) ? e.message : String(e)));
        return false;
    }
}

function main() {
    logDebug("==================================================");
    logDebug("Iniciando MCP Bridge Script Module (main)...");
    logDebug("==================================================");
    try {
        var netCount = ipc.network().getDeviceCount();
        logDebug("Acceso IPC verificado correctamente. Dispositivos actuales en topología: " + netCount);
    } catch (e) {
        logDebug("ADVERTENCIA al verificar IPC: " + e + " (Verifica que los Security Privileges estén marcados en la pestaña General).");
    }
    openBridgeWindow();
}

function cleanUp() {
    logDebug("Deteniendo MCP Bridge Script Module (cleanUp)...");
    try {
        if (typeof webViewManager !== "undefined" && webViewManager) {
            webViewManager.closeAll();
            logDebug("Todas las ventanas WebView del módulo fueron cerradas.");
        }
        bridgeWebView = null;
    } catch (e) {
        logDebug("Error en cleanUp(): " + e);
    }
}
