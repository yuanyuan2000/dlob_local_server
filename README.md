# dlob_local_server
A local server to fetch the current and historical market data

## Install the environment
1. Create a python virtual environment: ```virtualenv -p python3 .venv```
2. Activate the environment: ```source .venv/bin/activate```
3. Install the dependencies: ```pip install -r requirements.txt```
If you want to update the requirements.txt, just run ```pip freeze > requirements.txt```.


## Start the local server
1. If you run in python, please activate the environment and then just run ```python3 dlob_gateway.py```
2. If you want to run on the server, please create and move the service file to ```sudo mv dlob.service /etc/systemd/system/dlob.service```, an example of service file to run the dlob_gateway.py on .venv:
```
[Unit]
Description=Dlob Service

[Service]
# 使用绝对路径指定工作目录
WorkingDirectory=/home/ubuntu/drift/dlob_local_server
# 指定以哪个用户身份运行此服务
User=ubuntu
Group=ubuntu
# 使用虚拟环境中的Python解释器直接执行dlob_gateway.py脚本
ExecStart=/home/ubuntu/drift/dlob_local_server/.venv/bin/python3 /home/ubuntu/drift/dlob_local_server/dlob_gateway.py
# 当服务失败时自动重启
Restart=on-failure
# 为服务设置环境变量，如果有必要的话
# Environment=VAR1=value
# Environment=VAR2=value

[Install]
WantedBy=default.target
```
3. Some commands:
```
sudo systemctl daemon-reload  # 通知systemd有新的服务文件
```
```
sudo systemctl start dlob.service   # 启动服务
```
```
sudo systemctl stop dlob.service    # 停止服务
```
```
sudo systemctl restart dlob.service # 重启服务
```
```
sudo systemctl status dlob.service  # 查看服务状态
```
```
sudo journalctl -u dlob.service -n 10   # 查看最新的10条日志
```
```
sudo journalctl -u dlob.service -r    # 逆序查看日志
```