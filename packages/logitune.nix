# Logitune: cross-desktop control app for Logitech mice (MX Master/Anywhere).
# Not packaged in nixpkgs (verified 2026-08-04) — built from source here.
# Upstream: https://github.com/mmaher88/logitune
{ lib
, stdenv
, fetchFromGitHub
, cmake
, ninja
, pkg-config
, udev
, hidapi
, libusb1
, qt6
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "logitune";
  version = "0.3.7";

  src = fetchFromGitHub {
    owner = "mmaher88";
    repo = "logitune";
    rev = "7c633949f56e282b7055cba9e2ac61732a3c98c0"; # tag v0.3.7
    hash = "sha256-kjUerrbJQ/KMfvdvwB6Ix8FCqF3fOA6lDFureKkdO+o=";
  };

  # CMakeLists.txt has one hardcoded absolute install destination
  # (/etc/xdg/autostart) for the autostart .desktop file. Left as-is it
  # would make the install phase try to write outside $out (fails in the
  # Nix sandbox, and would be wrong on an immutable NixOS /etc anyway).
  # Redirect it under the store prefix instead.
  postPatch = ''
    substituteInPlace CMakeLists.txt \
      --replace "DESTINATION /etc/xdg/autostart" "DESTINATION etc/xdg/autostart"
  '';

  nativeBuildInputs = [
    cmake
    ninja
    pkg-config
    qt6.wrapQtAppsHook
  ];

  buildInputs = [
    udev # provides libudev.pc, required by CMakeLists (pkg_check_modules UDEV)
    hidapi
    libusb1
    qt6.qtbase # Core, Widgets, DBus, Network, Concurrent, Test
    qt6.qtdeclarative # Quick, QuickTest
    qt6.qtsvg # Svg
  ];

  cmakeFlags = [
    "-DCMAKE_BUILD_TYPE=Release"
    # fetchFromGitHub gives a tarball with no .git dir, so CMakeLists.txt's
    # `git describe` version detection can't run; it hard-fails without
    # this. Must be numeric X.Y.Z per the project's own version regex.
    "-DLOGITUNE_VERSION=${finalAttrs.version}"
    # Skip the GTest-based test suite (would pull in gtest and build
    # ~30 extra test binaries we never run in this derivation).
    "-DBUILD_TESTING=OFF"
  ];

  meta = with lib; {
    description = "Cross-desktop control app for Logitech mice (MX Master/Anywhere)";
    homepage = "https://github.com/mmaher88/logitune";
    license = licenses.gpl3Only;
    platforms = platforms.linux;
    mainProgram = "logitune";
  };
})
