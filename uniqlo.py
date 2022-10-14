# coding:utf-8
# python >= 3.5

import os
import random
import time
import requests
import json
import sys
import platform


class UniqloStockMonitor:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": 'application/json',
            "Connection": 'close',
            "Accept-Encoding": 'gzip, deflate, br',
            "Accept": 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            "Accept-Language": 'en-us',
            "User-Agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Safari/605.1.15'
        })

    @staticmethod
    def get_pid(name):
        return os.popen(f"ps -ef | grep \"{name} start\" " + "| grep -v grep | awk \'{print $2}\'").read().rstrip()

    @staticmethod
    def check_file(create=False, **kwargs):
        try:
            file = open('monitor_config.json', 'r')
            json.loads(file.read())
            file.close()
            return True
        except FileNotFoundError:
            if create:
                print("create")
                file = open('monitor_config.json', 'w+')
                file.write(json.dumps({
                    "products": {},
                    "push": kwargs
                }, ensure_ascii=False, indent=4))
                file.close()
            return False
        except json.decoder.JSONDecodeError:
            exit('文件格式错误，请删除配置文件！')

    @staticmethod
    def get_file_info(value='products'):
        try:
            file = open('monitor_config.json', 'r')
            json_file = json.loads(file.read())
            file.close()
            return json_file if value == 'all' else json_file[value]
        except KeyError:
            exit('配置文件有误！')

    def push_message(self, title, body):
        push_info = self.get_file_info('push')
        if push_info['type'] == 'bark':
            return requests.get(f"https://api.day.app/{push_info['key']}/{title}/{body}").json()

    def get_stock(self, product_code):
        """
        获取商品库存（仅快递库存）
        :return:
        """
        res = self._session.post('https://d.uniqlo.cn/p/stock/stock/query/zh_CN', data=json.dumps({
            "distribution": "EXPRESS",
            "productCode": product_code,
            "type": "DETAIL"
        }))

        return res.json()['resp'][0]['expressSkuStocks']

        # print(json.dumps(res.json(), ensure_ascii=False, indent=4))

    def get_activitys(self, product_code: str) -> list:
        """
        获取当前商品的活动
        :param product_code:
        :return:
        """
        res = self._session.get(f' https://d.uniqlo.cn/p/hmall-promotion-service/h/sale/calculation/'
                                f'groupOptionByProductCode/zh_CN?productCode={product_code}')

        effective_activitys = list()

        activitys = res.json()['resp'][0]['activitys']

        for i in activitys:
            try:
                if i['pageShow'] != None:
                    effective_activitys.append(i['pageShow'])
            except KeyError:
                continue

        return effective_activitys

    def get_product_info(self, product_code):
        """
        获取商品详情
        :product_code:
        :return:
        """
        res = self._session.get(f'https://d.uniqlo.cn/h/product/i/product/spu/h5/query/{product_code}/zh_CN')
        res_summary = res.json()['resp'][0]['summary']
        # print(res.json())
        data = {
            "name": res_summary['name'],
            'originPrice': res_summary['originPrice'],
            'gDeptValue': res_summary['gDeptValue'],
            'fullName': res_summary['fullName'],
            'listYearSeason': res_summary['listYearSeason'],
            'code': res_summary['code'],
            'rows': res.json()['resp'][0]['rows']
        }

        return data
        # print(json.dumps(data, ensure_ascii=False, indent=4))

    def search(self, product_id):
        return self._session.post('https://i.uniqlo.cn/p/hmall-sc-service/search/searchWithDescriptionAndConditions'
                                  '/zh_CN', data=json.dumps({
            "url": f"/search.html?description={product_id}",
            "pageInfo": {
                "page": '1',
                "pageSize": '24',
                "withSideBar": "Y"
            },
            "belongTo": "pc",
            "rank": "overall",
            "priceRange": {
                "low": '0',
                "high": '0'
            },
            "color": [],
            "size": [],
            "season": [],
            "material": [],
            "sex": [],
            "identity": [],
            "insiteDescription": "",
            "exist": [],
            "searchFlag": 'true',
            "description": product_id
        })).json()

    def get_goods_code(self, product_id, view_mode=False):
        """
        通过商品编号，列出商品所有型号并选择保存其具体的商品货号
        :param view_mode: bool 查看模式
        :param product_id: 4开头的6位code码
        :return: (商品代码, 商品详细信息, 现价, 商品型号)
        """
        search_result = self.search(product_id)
        if not len(search_result['resp'][1]):
            print("未找到商品，或该商品已下架！")
            return

        product_code_4_start = search_result['resp'][1][0]['code']  # 4开头的6位code码
        stock, product_info_rows, product_info = dict(), list(), dict()
        for result in search_result['resp'][1]:
            # 聚合搜索
            if result['code'] == product_code_4_start:
                product_code = result['productCode']
                # python version >= 3.5
                stock = {**stock, **self.get_stock(product_code)}
                product_info = self.get_product_info(result['productCode'])
                product_info_rows.append(product_info['rows'])
        print(f"{product_info['name']} {product_info['gDeptValue']} 原价: {product_info['originPrice']}")
        # zhCH
        # print(f"{search_result['resp'][1][0]['name4zhCN']} {search_result['resp'][1][0]['gender4zhCN']} "
        #       f"原价: {search_result['resp'][1][0]['originPrice']}")
        # print(json.dumps(product_info_rows, ensure_ascii=False, indent=4))
        # 商品数据整理
        rows = dict()
        for row in product_info_rows:
            for info in row:
                rows[info['sizeText']] = []

        for row in product_info_rows:
            for info in row:
                rows[info['sizeText']].append({
                    "style": info['style'],
                    "productId": info['productId'],
                    "varyPrice": info['varyPrice'],
                    "price": info['price']
                })
        # 查看
        # print(json.dumps(info, ensure_ascii=False, indent=4))
        if view_mode:
            for index, size in enumerate(rows):
                print(f"{size}")
                data_by_size = rows[list(rows.keys())[index]]
                for index, info in enumerate(data_by_size):
                    # print(info)
                    print(
                        f"  {info['style']} 现价:{info['price']} 库存:{stock[info['productId']]}")
            print()
            return

        for index, size in enumerate(rows):
            print(f"{index + 1}、{size}")

        choice = input("请选择码数: ")
        choice_size = list(rows.keys())[int(choice) - 1]

        data_by_size = rows[choice_size]
        vary_price = list()
        for index, info in enumerate(data_by_size):
            vary_price.append(info['varyPrice'])
            print(f"{index + 1}、{choice_size} {info['style']} 现价:{info['price']} 库存:{stock[info['productId']]}")
        choice = input("请选择颜色: ")

        goods_code = data_by_size[int(choice) - 1]['productId']
        choice_type = f"{choice_size} {data_by_size[int(choice) - 1]['style']}"
        print(f"已选择{choice_type}")
        return goods_code, product_info, vary_price[int(choice) - 1], choice_type

    def manage_product(self):
        if not self.check_file():
            exit('无配置文件！')
        while True:
            file_data = self.get_file_info('all')
            recorde_history = file_data['products']
            recorde_list = list()
            for index, goods_code in enumerate(recorde_history):
                print(f"{index + 1}、{'库存监控' if recorde_history[goods_code]['targetPrice'] == '' else '降价监控'} "
                      f"【{recorde_history[goods_code]['type']}】{recorde_history[goods_code]['name']} "
                      f"{recorde_history[goods_code]['code']}")
                recorde_list.append(goods_code)
            print(f"{len(recorde_history) + 1}、退出")
            choice = input("请选择要修改的商品: ")
            if int(choice) == len(recorde_history) + 1:
                return
            print('已选择:', end='')
            print(
                f"【{recorde_history[recorde_list[int(choice) - 1]]['type']}】{recorde_history[recorde_list[int(choice) - 1]]['name']} "
                f"{recorde_history[recorde_list[int(choice) - 1]]['code']}")

            depreciate_warning = False if recorde_history[recorde_list[int(choice) - 1]]['targetPrice'] == '' else True
            change_choice = input(f"  1、更改为{'库存监控' if depreciate_warning else '降价监控'}\n"
                                  f"  2、删除\n请选择: ")
            if change_choice == '1':
                # 当前为降价监控，更改为库存
                if depreciate_warning:
                    recorde_history[recorde_list[int(choice) - 1]]['targetPrice'] = ''
                    print('已经更改为库存监控！')
                else:
                    recorde_history[recorde_list[int(choice) - 1]]['targetPrice'] = \
                        input('设置降价目标价(当前价格小于或等于此价格时触发提醒): ')
                    print('设置成功！')
            elif change_choice == '2':
                del recorde_history[recorde_list[int(choice) - 1]]
                print('已删除！')
            else:
                print('选择错误，请重试')
                continue
            monitor_recorde = open('monitor_config.json', 'w')

            write_data = json.dumps({
                "products": recorde_history,
                "push": file_data['push']
            }, ensure_ascii=False, indent=4)

            monitor_recorde.write(write_data)
            monitor_recorde.close()

    def add_monitor_product(self):

        if not self.check_file():
            self.check_file(True, type='bark', key=input('请输入bark的设备码: '))

        code = input("请输入商品货号(4开头的6位数字)：")
        goods_code, product_info, vary_price, choice_type = self.get_goods_code(code)
        if goods_code is not None:
            target_price = input("设置降价目标价(当前价格小于或等于此价格时触发提醒，回车跳过): ")
            file_data = self.get_file_info('all')
            recorde_history = file_data['products']
            recorde_history[goods_code] = {
                "name": product_info['name'],
                "type": choice_type,
                "originPrice": product_info['originPrice'],
                "varyPrice": vary_price,
                "targetPrice": target_price,
                "code": product_info['code']
            }
            monitor_recorde = open('monitor_config.json', 'w+')

            write_data = json.dumps({
                "products": recorde_history,
                "push": file_data['push']
            }, ensure_ascii=False, indent=4)

            monitor_recorde.write(write_data)
            monitor_recorde.close()

            print("写入成功！")

    def main(self):
        while True:
            # self.get_goods_code(product_id)
            choice = input("1、查找商品并查看商品库存\n"
                           "2、查找并添加需要监控的商品\n"
                           "3、查看并管理监控的商品\n"
                           "4、开始监控\n"
                           "请输入序号: ")
            if choice == '1':
                self.get_goods_code(input("请输入商品货号(4开头的6位数字)："), view_mode=True)
            if choice == '2':
                self.add_monitor_product()
            elif choice == '3':
                self.manage_product()
            elif choice == '4':
                self.monitor()
            else:
                print('错误！')

    def check_stock(self, goods_list):
        for goods_code in goods_list:
            time.sleep(random.randint(1, 3))
            product_id = goods_code[:-3]
            stocks = self.get_stock(product_id)[goods_code]
            product_info = self.get_product_info(product_id)
            choice_product_info = [i for i in product_info['rows'] if i['productId'] == goods_code][0]

            vary_price = choice_product_info['price']

            goods_recorde_info = goods_list[goods_code]
            target_price = goods_recorde_info['targetPrice']
            # 当值不能被强制转换为数值时，则不监控降价
            try:
                float(target_price)
                depreciate_warning = True
            except ValueError:
                depreciate_warning = False

            print(f"{'降价监控: ' if depreciate_warning else '库存监控: '}"
                  f"【{choice_product_info['style']} | 库存: {stocks} ｜ {choice_product_info['size']}】{product_info['name']}")

            push_message = f"【{choice_product_info['style']} | {choice_product_info['size'].replace('/', ' ')}】" \
                           f"{product_info['name']} {product_info['code']}\n" \
                           f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} 当前库存: {stocks} 价格: {vary_price}" \
                           f"?group=Uniqlo&icon=https://www.uniqlo.cn/public/Image/L1/nav/nav-logo/LOGO.gif" \
                           f"&url=https://www.uniqlo.cn/product-detail.html?" \
                           f"productCode={choice_product_info['productId'][:-3]}&productId={choice_product_info['productId']}"
            # 降价
            if depreciate_warning and stocks:
                if float(target_price) >= float(vary_price):
                    print(f"【{choice_product_info['style']} | {choice_product_info['size']}】{product_info['name']} ",
                          end='')
                    print(f"当前库存: {stocks}")
                    print(f"当前价格: {vary_price}")
                    self.push_message('优衣库降价库存监控', push_message)

            elif stocks:
                print(f"【{choice_product_info['style']} | {choice_product_info['size']}】{product_info['name']} ",
                      end='')
                print(f"当前库存: {stocks}")
                # TODO 创建订单报错
                # creat_order(choice_product_info)
                self.push_message('优衣库库存监控', push_message)

    def monitor(self):
        if not self.check_file():
            exit("请先添加需要监控的商品！")
        recorde_history = self.get_file_info()
        # print(recorde_history)

        print('已选择:')
        for index, goods_code in enumerate(recorde_history):
            product_id = goods_code[:-3]

            stocks = self.get_stock(product_id)[goods_code]
            product_info = self.get_product_info(product_id)

            choice_product_info = [i for i in product_info['rows'] if i['productId'] == goods_code][0]

            print(f"【{choice_product_info['sizeText']}|{choice_product_info['style']}】"
                  f"{product_info['name']}  {product_info['code']}")
            print('****************活动****************')
            print("\n".join(self.get_activitys(product_id)))
            print('************************************')
            # activity = ",".join(self.get_activitys(product_id))

            print(f"原价: {product_info['originPrice']} 现价: {choice_product_info['price']}")
            # print('开始监控库存...')
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} 当前库存: {stocks}")
            if len(recorde_history) - 1 != index:
                print('--------------------------------------------')

        print('-----------------开始监控库存-----------------')
        self.push_message('优衣库监控已启动', '')
        while True:
            print(time.strftime("%m-%d %H:%M:%S", time.localtime()))
            hour = time.strftime('%H', time.localtime())
            sleep_time = random.randint(10, 30) \
                if hour not in ['03', '04', '05', '06'] else random.randint(40, 60)
            try:
                self.check_stock(recorde_history)
            except KeyboardInterrupt:
                print('KeyboardInterrupt')
                return
            except:
                print("出错，重试！")
            time.sleep(sleep_time * 60 if sleep_time >= 40 else sleep_time)


if __name__ == '__main__':
    uniqlo = UniqloStockMonitor()
    uniqlo.check_file()
    args = sys.argv

    # 如需命令行模式，取消注释
    # uniqlo.main()

    if len(args) == 1:
        print(f"""
        Usage: python {args[0]} <option>
        option can be:
        \tsearch: Search for products and view product inventory
        \tconfig: Add products to be monitored
        \tmodify: Edit config file and notification
        \tstart:  Start to monitor
        \tostart: One-click start, support Linux
        \tstop:   Stop the one-click start process
        """)
        exit(1)

    elif args[1] == "search":
        if len(args) > 2:
            uniqlo.get_goods_code(args[2], view_mode=True)
        else:
            uniqlo.get_goods_code(input("请输入商品货号(4开头的6位数字)："), view_mode=True)

    elif args[1] == "config":
        uniqlo.add_monitor_product()

    elif args[1] == "modify":
        uniqlo.manage_product()

    elif args[1] == "start":
        uniqlo.monitor()

    elif args[1] == 'ostart':
        if platform.system() not in ['Linux', 'Darwin']:
            exit(f'Linux/Darwin only, your system version is {platform.system()}')

        os.system(f'nohup python3 {args[0]} start > nohup.out 2>&1 &')
        pid = uniqlo.get_pid(args[0])
        if pid != '':
            print(f"监控已启动, PID: {pid}")

    elif args[1] == 'stop':
        pid = uniqlo.get_pid(args[0])
        if pid == '':
            exit('监控未启动！')
        os.system(f"kill -9 '{pid.rstrip()}'")
        pid = uniqlo.get_pid(args[0])

        if pid == '':
            print('已结束进程！')
    else:
        exit('Nothing to do.')

