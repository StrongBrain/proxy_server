"""
 Usage:
 A call to http://localhost:80000/test will cache in memcache for TTL seconds
 and not redownload it again. Host, port and TTL may be configured via
 command line arguments or via configuration file.
 To stop the server simply send SIGINT (Ctrl-C). It does not handle any headers or post data.

"""

from optparse import OptionParser

import BaseHTTPServer
import ConfigParser
import logging
import memcache
import requests


CONF_FILE = 'proxy_server.cfg'
REQUEST_TIMEOUT = 408
SERVICE_UNAVAILABLE = 503

log = logging.getLogger(__name__) # pylint: disable=invalid-name
config = ConfigParser.ConfigParser() # pylint: disable=invalid-name
config.read(CONF_FILE)

TTL = config.getint('proxy_server', 'TTL')

class CachingHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """ Custom handler for caching proxy server. """

    def __init__(self, *args, **kwargs):
        # Setup memcache client
        self._mhost = config.get('memcached', 'host')
        self._mport = config.getint('memcached', 'port')
        self._mc = memcache.Client([(self._mhost, self._mport)])

        BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def do_GET(self): # pylint: disable=invalid-name
        """ Overwrite do_GET method. """
        data = ''
        if self._mc.get(self.path):
            # Get response from memcache
            data = self._mc.get(self.path)
            status_code = data.status_code # pylint: disable=no-member
        else:
            # Setup proxy server request URL
            host, port = self.server.server_address
            proxy_server = 'http://{0}:{1}'.format(host, port)
            url = proxy_server + self.path
            try:
                # Fetch data from the proxy server and add it to memcache
                data = requests.get(url, timeout=20)
                self._mc.set(self.path, data, time=TTL)
                status_code = data.status_code
            except requests.exceptions.ConnectionError as e: # pylint: disable=invalid-name
                log.info(e)
                status_code = SERVICE_UNAVAILABLE
            except requests.exceptions.Timeout as e: # pylint: disable=invalid-name
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
               -  script_name - server.py
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
        global TTL # pylint: disable=global-statement
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
