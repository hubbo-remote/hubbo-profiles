# Sourced by the tools/bin scripts: the repo root, and in_docker to run a command in the tools image.
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# in_docker <mode> <command...>: run in the tools image with the repo at /repo.
#   rw: the repo writable; ro: read-only; build: read-only with build/ writable.
in_docker() {
  local mode="$1" mounts
  shift
  case "$mode" in
    rw) mounts=(-v "$root:/repo") ;;
    ro) mounts=(-v "$root:/repo:ro") ;;
    build) mkdir -p "$root/build"; mounts=(-v "$root:/repo:ro" -v "$root/build:/repo/build") ;;
  esac
  local image
  image="$("$root/tools/bin/tools-image")"
  exec docker run --rm -u "$(id -u):$(id -g)" "${mounts[@]}" ${EXTRA_MOUNTS[@]+"${EXTRA_MOUNTS[@]}"} "$image" "$@"
}
