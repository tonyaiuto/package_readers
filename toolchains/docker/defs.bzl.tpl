"""toolchain to provide the docker binary."""

DockerInfo = provider(
    doc = """Information needed to invoke docker.""",
    fields = {
        "name": "The name of the toolchain",
        "valid": "Is this toolchain valid and usable?",
        "path": "The path to a pre-built docker",
    },
)

def _docker_toolchain_impl(ctx):
    toolchain_info = platform_common.ToolchainInfo(
        docker = DockerInfo(
            name = str(ctx.label),
            valid = bool(ctx.attr.docker_path),
            path = ctx.attr.docker_path,
        ),
    )
    return [toolchain_info]

docker_toolchain = rule(
    implementation = _docker_toolchain_impl,
    attrs = {
        "docker_path": attr.string(doc = "The path to the docker executable."),
    },
)
