{
  description = "Ziv video clipping development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forEachSystem = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in {
      devShells = forEachSystem (pkgs: {
        default = pkgs.mkShell {
          packages = [
            pkgs.python311
            pkgs.ffmpeg
            pkgs.uv
          ];
          shellHook = ''
            export UV_PYTHON_PREFERENCE=only-system
            export PATH="$PWD/.venv/bin:$PATH"
          '';
        };
      });
    };
}
