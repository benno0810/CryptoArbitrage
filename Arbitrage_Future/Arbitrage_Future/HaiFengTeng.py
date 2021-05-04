from hft_rest_api.python import restapi


class HaiFengTeng:
    def __init__(self,config):
        self.name = config["HFT"]["name"]
        self.signature = config["HFT"]["signature"]

    def login(self):
        print restapi.get_account(self.name, self.signature)
        # print self.name
        # print self.signature