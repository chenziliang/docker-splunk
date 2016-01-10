#!/bin/bash

set -e

sudo mkdir -p /tmp/


add_forwarder_servers() {
    if [[ -n ${1} ]]; then
        for fserver in `echo ${1} | sed "s#,# #g"`
        do
            if ! sudo -HEu ${SPLUNK_USER} ${SPLUNK_HOME}/bin/splunk list forward-server -auth admin:admin | grep -q "${fserver}"; then
                sudo -HEu ${SPLUNK_USER} ${SPLUNK_HOME}/bin/splunk add forward-server "${fserver}" -auth admin:admin
            else
                echo "${fserver} has already been added"
            fi
        done
    fi
}


start_service() {
    # If user changed SPLUNK_USER to root we want to change permission for SPLUNK_HOME
    if [[ "${SPLUNK_USER}:${SPLUNK_GROUP}" != "$(stat --format %U:%G ${SPLUNK_HOME})" ]]; then
        chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} ${SPLUNK_HOME}
    fi

    # If these files are different override etc folder (possible that this is upgrade or first start cases)
    # Also override ownership of these files to splunk:splunk
    if ! $(cmp --silent /var/opt/splunk/etc/splunk.version ${SPLUNK_HOME}/etc/splunk.version); then
        cp -fR /var/opt/splunk/etc ${SPLUNK_HOME}
        chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} ${SPLUNK_HOME}/etc
        chown -R ${SPLUNK_USER}:${SPLUNK_GROUP} ${SPLUNK_HOME}/var
    fi

    sudo -HEu ${SPLUNK_USER} ${SPLUNK_HOME}/bin/splunk start --accept-license --answer-yes --no-prompt
    if [ -e "/tmp/splunk_pass_changed" ]; then
        echo "password changed"
    else
        sudo touch /tmp/splunk_pass_changed
        sudo -HEu ${SPLUNK_USER} ${SPLUNK_HOME}/bin/splunk edit user admin -password admin -auth admin:changeme
    fi

    trap "sudo -HEu ${SPLUNK_USER} ${SPLUNK_HOME}/bin/splunk stop" SIGINT SIGTERM EXIT
    add_forwarder_servers "${SPLUNK_FORWARD_SERVER}"

    sudo -HEu ${SPLUNK_USER} tail -n 0 -f ${SPLUNK_HOME}/var/log/splunk/splunkd_stderr.log &
}


######### Main function ##########

if [ "$1" = 'splunk' ]; then
    shift
    sudo -HEu ${SPLUNK_USER} ${SPLUNK_HOME}/bin/splunk "$@"
elif [ "$1" = 'start-service' ]; then
    start_service
    wait
else
    "$@"
fi
