// Vivagg: carga la extensión (sin firmar) como complemento temporal en cada arranque de Firefox.
// El Firefox oficial exige firma de Mozilla para instalar de forma permanente; los complementos temporales no.
// keepStorageOnUninstall/keepUuidOnUninstall conservan ajustes y datos de la extensión entre reinicios
// (un complemento temporal se desinstala al cerrar Firefox).
// Lo ejecuta mozilla.cfg (autoconfig, privilegiado); ver ./default.nix.
try {
  const Ci = Components.interfaces;
  const observers = Components.classes["@mozilla.org/observer-service;1"].getService(Ci.nsIObserverService);
  defaultPref("extensions.webextensions.keepStorageOnUninstall", true);
  defaultPref("extensions.webextensions.keepUuidOnUninstall", true);

  const topic = "sessionstore-windows-restored";
  const observer = {
    observe() {
      observers.removeObserver(observer, topic);
      const dir = Components.classes["@mozilla.org/file/local;1"].createInstance(Ci.nsIFile);
      dir.initWithPath("@VIVAGG_EXTENSION_DIR@");
      if (!dir.exists()) return;
      const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
      AddonManager.installTemporaryAddon(dir).catch(error => Components.utils.reportError(error));
    },
  };
  observers.addObserver(observer, topic);
} catch (error) {
  Components.utils.reportError(error);
}
