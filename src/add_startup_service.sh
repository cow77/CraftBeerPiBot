INSTALL_PATH=$(realpath $(dirname $0))
SCRIPT_PATH=${INSTALL_PATH}/config/craftbeerpibot.service
EXEC_PATH=${INSTALL_PATH}/crafteerpibot.py
LOG_PATH=${INSTALL_PATH}/stdout.log

if [ "$#" -gt 0 ]; then
	SELECTED_USER=$1
else
	SELECTED_USER=$USER
fi

sudo cp ${SCRIPT_PATH} /etc/systemd/system/craftbeerpibot.service
sudo sed -i 's@SERVER_PLACEHOLDER@'"$EXEC_PATH"'@g' /etc/systemd/system/craftbeerpibot.service
sudo sed -i 's@LOG_PLACEHOLDER@'"$LOG_PATH"'@g' /etc/systemd/system/craftbeerpibot.service
sudo sed -i 's@WORKING_DIR_PLACEHOLDER@'"$INSTALL_PATH"'@g' /etc/systemd/system/craftbeerpibot.service
sudo sed -i 's@USER_PLACEHOLDER@'"$SELECTED_USER"'@g' /etc/systemd/system/craftbeerpibot.service

sudo systemctl daemon-reload
sudo systemctl enable craftbeerpibot.service
sudo systemctl stop craftbeerpibot.service
sudo systemctl start craftbeerpibot.service

