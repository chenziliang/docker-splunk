#!/usr/bin/python

import ConfigParser as cp
import argparse as ap
import subprocess
import os.path as op


def package_name(splunk_params):
    return "splunk-{version}-{build}-Linux-x86_64.tgz".format(
        version=splunk_params["version"],
        build=splunk_params["build"])


def download_splunk_package(splunk_params):
    package = package_name(splunk_params)
    md5_package = "{package}.md5".format(package=package)
    for package in (package, md5_package):
        if op.exists(package):
            print "{package} has already downloaded".format(package=package)
            continue

        print "Downloading {}".format(package)
        url = ("https://download.splunk.com/products/splunk/releases/"
               "{version}/{product}/linux/{package}").format(
                   version=splunk_params["version"],
                   product=splunk_params["product"],
                   package=package)
        res = subprocess.Popen(["wget", "-qO", package, url],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE).communicate()
        if res[1]:
            msg = "Faile to download {package}, error={error}".format(
                package=package, error=res[1])
            raise Exception(msg)

    print "Verify md5sum for {package}".format(package=package)
    subprocess.check_call(["md5sum", "-c", package])


def pre_common_dockerfile_data(splunk_params):
    package = package_name(splunk_params)
    env_package = "ENV SPLUNK_FILENAME {package}".format(package=package)
    return [
        "MAINTAINER Ken Chen <zlchen.ken@gmail.com>\n",
        env_package,
        "ENV SPLUNK_ROOT /opt/",
        "ENV SPLUNK_HOME /opt/splunk",
        "ENV SPLUNK_GROUP splunk",
        "ENV SPLUNK_USER splunk",
        "ENV SPLUNK_BACKUP_DEFAULT /var/opt/splunk",
        "ENV LANG en_US.utf8",
        "\n# Add splunk:splunk user",
        """RUN groupadd -r ${SPLUNK_GROUP} && """
        """useradd -r -m -g ${SPLUNK_GROUP} ${SPLUNK_USER}"""
    ]


def post_common_dockerfile_data(splunk_params):
    apps = splunk_params["apps"]
    if apps:
        apps = [app.strip() for app in apps.split(",")]

    if apps:
        apps = ["ADD {app} ${{SPLUNK_HOME}}/etc/apps/\n".format(app=app)
                for app in apps]
    else:
        apps = []

    data = [
        "\n# ADD official Splunk release, unzip in /opt/splunk",
        "# Also backup etc folder, so it will be later copied to the linked volume",
        "RUN mkdir -p ${SPLUNK_HOME}",
        "ADD ${SPLUNK_FILENAME} ${SPLUNK_ROOT}",
    ]
    data.append("\n# Apps")
    data.extend(apps)

    data.extend([
        """RUN mkdir -p /var/opt/splunk \\\n"""
        """    && cp -R ${SPLUNK_HOME}/etc ${SPLUNK_BACKUP_DEFAULT} \\\n"""
        """    && chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} ${SPLUNK_BACKUP_DEFAULT} \\\n"""
        """    && rm -rf /var/lib/apt/lists/*""",
        "\nCOPY entrypoint.sh /sbin/entrypoint.sh",
        "RUN chmod +x /sbin/entrypoint.sh",
        "\n# Ports Splunk Web, Splunk Daemon, KVStore, "
                "Splunk Indexing Port, Network Input, HTTP Event Collector",
        "EXPOSE 8000/tcp 8089/tcp 8191/tcp 9997/tcp 1514 8088/tcp",
        "WORKDIR /opt/splunk",
        "\n# Configurations folder, var folder for everyting "
                "(indexes, logs, kvstore)",
        """VOLUME ["/opt/splunk/etc", "/opt/splunk/var"]""",
        "\n# Forwarder servers",
        """ENV SPLUNK_FORWARD_SERVER {forwarder_servers}""".format(
            forwarder_servers=splunk_params["forwarder_servers"]),
        "\nRUN mkdir -p ${SPLUNK_HOME}/var && "
        "chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} ${SPLUNK_HOME}\n",
        """ENTRYPOINT ["/sbin/entrypoint.sh"]""",
        """CMD ["start-service"]""",
    ])
    return data


def write_dockerfile_for_ubuntu(splunk_params, f):
    data = ["# Generated by dokerfile_gen.py\n"]
    data.append("FROM ubuntu:trusty\n")
    data.extend(pre_common_dockerfile_data(splunk_params))
    data.append("""\n# Make the "en_US.UTF-8" locale so splunk will """
                """be utf-8 enabled by default""")
    data.append("""RUN apt-get update && apt-get install -y locales \\\n"""
                """    && localedef -i en_US -c -f UTF-8 -A """
                """/usr/share/locale/locale.alias en_US.UTF-8""")
    data.append("\n# pdfgen dependency")
    data.append("RUN apt-get install -y libgssapi-krb5-2")
    data.extend(post_common_dockerfile_data(splunk_params))

    f.write("\n".join(data))


def generate_dockerfile_for_ubuntu(splunk_params):
    dockerfile = "Dockerfile.ubuntu"
    print "Generating Dockerfile for {dockerfile}".format(
        dockerfile=dockerfile)
    with open(dockerfile, "w") as f:
        write_dockerfile_for_ubuntu(splunk_params, f)


def write_dockerfile_for_centos(splunk_params, f):
    pass


def generate_dockerfile_for_centos(splunk_params):
    with open("Dockerfile.centos", "w") as f:
        write_dockerfile_for_centos(splunk_params, f)


def do_generate(splunk_params):
    download_splunk_package(splunk_params)
    if splunk_params["linux"] == "centos":
        generate_dockerfile_for_centos(splunk_params)
    else:
        generate_dockerfile_for_ubuntu(splunk_params)


def generate_dockerfile(conf):
    parser = cp.ConfigParser()
    parser.read(conf)
    stanza_name = "splunk"
    splunk_params = {
        "linux": None,
        "product": None,
        "version": None,
        "build": None,
        "forwarder_servers": None,
        "apps": None
    }
    required = ("product", "version", "build")

    for key in splunk_params.iterkeys():
        val = parser.get(stanza_name, key, "")
        if key in required and not val:
            raise Exception("Required param=%s is not set in conf=%s",
                            key, conf)
        splunk_params[key] = val

    do_generate(splunk_params)


def main():
    parser = ap.ArgumentParser(description="Dockfiler generator args")
    parser.add_argument("--file", type=str, dest="conf",
                        default="dockerfile_gen.conf", required=False,
                        help="The conf file of this generator which defines "
                        "splunk parameters")
    args = parser.parse_args()
    generate_dockerfile(args.conf)


if __name__ == "__main__":
    main()