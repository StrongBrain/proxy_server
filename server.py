from optparse import OptionParser

import BaseHTTPServer
import ConfigParser
import logging
import memcache
import requests


CONFIG = 'proxy_server.cfg'
REQUEST_TIMEOUT = 408
SERVICE_UNAVAILABLE = 503

log = logging.getLogger(__name__)
config = ConfigParser.ConfigParser()
config.read(CONFIG)

TTL = config.getint('proxy_server', 'TTL')

class CachingHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        # Setup memcache client
        self._mhost = config.get('memcached', 'host')
        self._mport = config.getint('memcached', 'port')
        self._mc = memcache.Client([(self._mhost, self._mport)])

        BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def do_GET(self):
        data = ''
        if self._mc.get('sample_request'):
            # Get response from memcache
            data = self._mc.get('sample_request')
            status_code = data.status_code # pylint: disable=no-member
        else:
            # Setup proxy server request URL
            host, port = self.server.server_address
            proxy_server = 'http://{0}:{1}'.format(host, port)
            url = proxy_server + self.path
            try:
                # Fetch data from the proxy server and add it to memcache
                data = requests.get(url, timeout=20)
                self._mc.set('sample_request', data, time=TTL)
                status_code = data.status_code
            except requests.exceptions.ConnectionError as e:
                log.info(e)
                status_code = SERVICE_UNAVAILABLE
            except requests.exceptions.Timeout as e:
                log.info(e)
                status_code = REQUEST_TIMEOUT

        # Send response to the client
        self.send_response(status_code)
        self.end_headers()
        self.wfile.writelines(data)

def run():
    """ Run a simple proxy server with caching. """
    # Parse arguments from command line.
    usage = """ Usage: <script_name> -s <server> -p <port> -t <ttl>.
               -  script_name - proxy_server.py
               -  server - IP address of running proxy server
               -  port - port where some server is running
               -  ttl - Time To Live ( time for caching requests).
            """
    parser = OptionParser(usage=usage)
    parser.add_option("-s", "--server", dest="server",
                      help="setup proxy server(via IP address)")
    parser.add_option("-p", "--port", dest="port",
                      help="setup port of proxy server")
    parser.add_option("-t", "--ttl", dest="ttl",
                      help="time for caching requests")
    opts, _ = parser.parse_args()

    if opts.server and opts.port and opts.ttl:
        # Get configurations from command line
        host = opts.server
        port = int(opts.port)
        global TTL
        TTL = int(opts.ttl)
    else:
        parser.print_usage()
        print "Used configuration file: proxy_server.cfg"

        # Load configs from config file
        host = config.get('proxy_server', 'host')
        port = config.getint('proxy_server', 'port')

    # Run proxy server.
    httpd = BaseHTTPServer.HTTPServer((host, port), CachingHandler)
    httpd.serve_forever()

if __name__ == '__main__':
    run()
