import re
from core.common import get_table_form


class Cli:
    def __init__(self):
        self.t_depth = 0
        self.c_depth = 0

    def options(self, name, **attrs):
        self.t_depth += 1

        def wrapper(func):
            def inner(cls, *args, **kwargs):
                self.c_depth += 1
                kwargs.update({name: attrs})
                if self.c_depth == self.t_depth:
                    cls.root(f'开始进入终端模式 [quit:退出|help:帮助|run:运行]{" " * 10}')
                    print(f"\n    {cls.__info__.get('desc', '暂无关于此漏洞的描述信息')}\n")
                    while True:
                        keyword = input('shell>')
                        if keyword in ['quit', 'exit']:
                            break
                        elif keyword in ['help', '?']:
                            data = [{'变量': k, '描述': v["desc"], '赋值': v["default"]} for k, v in kwargs.items()]
                            tb = get_table_form(data, border=False)
                            print(tb)
                            print('\n语法: set {变量} {赋值}\n')
                        elif keyword in ['exploit', 'run']:
                            args = tuple([_['default'] for _ in kwargs.values()])
                            try:
                                res = func(cls, *args)
                                print(res)
                            except Exception as e:
                                cls.warn(e)
                        else:
                            match = re.match(r'set ([\w-]+)[ :=]?(.*)', keyword)
                            if match:
                                _name, _value = match.group(1), match.group(2)
                                if _name in kwargs.keys():
                                    kwargs[_name]['default'] = _value
                                else:
                                    print("[-] 变量错误")
                            else:
                                print("[-] 语法错误")
                else:
                    return func(cls, **kwargs)

            return inner

        return wrapper
