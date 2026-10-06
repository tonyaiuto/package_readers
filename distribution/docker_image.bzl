# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""docker_image_from_tar - build a docker image from a tar using the docker CLI."""

def _docker_image_from_tar_impl(ctx):
    docker = ctx.toolchains["@docker_tools//:docker_toolchain_type"].docker
    if not docker.valid:
        fail("No docker CLI available on this machine.")

    output = ctx.outputs.out

    # docker.path is a plain string pointing at the system binary found via
    # `which` (see //toolchains/docker:configure.bzl) -- it isn't a
    # Bazel-tracked File, so it must not be added to `inputs`.
    ctx.actions.run(
        mnemonic = "DockerImage",
        progress_message = "Building docker image %s" % ctx.label,
        executable = ctx.executable._builder,
        arguments = [docker.path, ctx.file.src.path, output.path],
        inputs = [ctx.file.src],
        outputs = [output],
        # docker needs the user's environment (e.g. PATH for credential
        # helpers, DOCKER_HOST) and talks to a daemon outside the sandbox.
        use_default_shell_env = True,
        execution_requirements = {
            "local": "1",
            "no-remote": "1",
        },
    )
    return [DefaultInfo(files = depset([output]))]

docker_image_from_tar = rule(
    implementation = _docker_image_from_tar_impl,
    doc = "Builds a `FROM scratch` docker image from a tar and `docker save`s it.",
    attrs = {
        "out": attr.output(
            doc = "Output path for the `docker save`d image.",
            mandatory = True,
        ),
        "src": attr.label(
            doc = "Tar of files, rooted at /, to ADD to the image.",
            mandatory = True,
            allow_single_file = [".tar"],
        ),
        "_builder": attr.label(
            default = ":build_docker_image.sh",
            executable = True,
            cfg = "exec",
            allow_single_file = True,
        ),
    },
    toolchains = ["@docker_tools//:docker_toolchain_type"],
)
