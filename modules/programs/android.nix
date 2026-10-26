# Toolchain Android para exportar APK desde Godot 4.7 (Se oye todo, 26-10).
# Versiones = android_source.zip de Godot 4.7: compileSdk 36, build-tools 36.1.0, JDK 17.
# Sin NDK: Godot usa las .so precompiladas; AGP solo avisa de que no las "stripea".
# Licencia del Android SDK aceptada por Alexis el 26-10-2026.
{ pkgs, ... }:

let
  android = pkgs.androidenv.composeAndroidPackages {
    platformVersions = [ "36" ];
    buildToolsVersions = [ "36.1.0" ];
    includeEmulator = false;
    includeSources = false;
    includeNDK = false;
  };
  sdk = "${android.androidsdk}/libexec/android-sdk";
in
{
  nixpkgs.config.android_sdk.accept_license = true;

  environment.systemPackages = [
    android.androidsdk # adb, sdkmanager, apksigner, aapt2 (parcheados para NixOS)
    pkgs.jdk17
  ];

  environment.variables = {
    ANDROID_HOME = sdk;
    ANDROID_SDK_ROOT = sdk;
    JAVA_HOME = pkgs.jdk17.home;
  };
}
