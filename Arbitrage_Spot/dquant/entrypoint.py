import argparse
import logging
from logging.handlers import RotatingFileHandler


from dquant.datafeed import Datafeed


class EntryPoint:
    datafeed = None

    def exec_command(self, args ):
        logging.debug('exec_command:%s' % args)

        if "feed" in args.command:
            self.datafeed = Datafeed()
            if args.markets:
                self.datafeed.init_markets(args.markets.split(","))
            self.datafeed._run_loop()
            return


    def init_logger(self, args):
        level = logging.INFO
        if args.debug:
            level = logging.DEBUG
        logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                            level=level)
        Rthandler = RotatingFileHandler('../logs/dquant.log', maxBytes=100 * 1024 * 1024, backupCount=10)
        Rthandler.setLevel(level)
        formatter = logging.Formatter('%(asctime)-12s [%(levelname)s] %(message)s')
        Rthandler.setFormatter(formatter)
        logging.getLogger('').addHandler(Rthandler)

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-d", "--debug", help="debug verbose mode",
                            action="store_true")
        parser.add_argument("-m", "--markets", type=str,
                            help="markets, example: -mokexusd")
        parser.add_argument("-s","--strategy",type=str,
                            help="strategy, example:-smaker")
        parser.add_argument("command", nargs='*', default="watch",
                            help='verb: "feed|exec|rexec"')
        args = parser.parse_args()
        self.init_logger(args)
        self.exec_command(args)
        print('main end')
        exit(-1)


def main():
    entrypoint = EntryPoint()
    entrypoint.main()

if __name__ == "__main__":
    main()
