""" Config module

Used to parse, store and handle configuration properties
"""

import os
import sys

# Get the right config parser
if sys.version_info > (3, 0):
    import configparser
else:
    import ConfigParser


__all__ = ["Config"]

# XXX: www and cgi folder should be relative to this file - not the best solution
file_dir = os.path.dirname(__file__)

class Config(object):
    """Configuration helper"""
    def __init__(self):
        """Creates the properties dictionary"""
        self._properties = {}

    def set(self, key, value):
        """Set property by key and value"""
        self._properties[key] = value

    def get(self, key, default=None):
        """Get property by key; default is default return value"""
        return self._properties.get(key, default)

    def print_config(self):
        """Prints property value pairs for each defined property"""
        for key in self._properties:
            print("{:<20} {}".format(key, self.get(key)))

    def defaults(self):
        """Sets the default properties' settings"""
        self.set('HOST', '')
        self.set('PORT', 8000)
        self.set('REQ_BUFFSIZE', 4096)
        self.set('MAX_URL', 1024)
        self.set('HTTP_VERSION', 1.0)
        self.set('PUBLIC_DIR', os.path.join(file_dir, 'www'))
        self.set('CGI_DIR', os.path.join(file_dir, 'www/cgi-bin'))
        self.set('INDEX_FILES', ['index.html', 'index.htm'])
        # NOTE: The following are currently unused
        self.set('LOGGING', True)
        self.set('LOG_FILE', 'server.log')

    def file(self, file_path):
        """Sets properties' settings via configuration file"""
        self.defaults()
        if os.path.isfile(file_path):
            # Python 3.^
            if sys.version_info > (3, 0):
                config = configparser.ConfigParser()
                config.read(file_path)
                if "server" in config:
                    for key in config["server"]:
                        try:
                            value = config["server"][key]
                            if key.upper() == "PORT" or key.upper() == "REQ_BUFFSIZE":
                                value = int(value)
                            elif key.upper() == "HTTP_VERSION":
                                value = float(config["server"][key])
                            elif key.upper() == "INDEX_FILES":
                                value = config["server"][key].split()
                            elif key.upper() == "PUBLIC_DIR" or \
                                    key.upper() == "CGI_DIR":
                                value = self._abs_dir(value)
                            else:
                                value = str(config["server"][key])
                            self.set(key.upper(), value)
                        except ValueError:
                            raise
                else:
                    print("* Wrong or incorrect configuration")
                    print("* Assuming default settings")
            # Python 2.^
            else:
                with open(file_path, "rb") as f:
                    config = ConfigParser.ConfigParser()
                    config.readfp(f)
                    try:
                        for pair in config.items("server"):
                            try:
                                key, value = pair[0], pair[1]
                                if key.upper() in ["PORT", "REQ_BUFFSIZE"]:
                                    value = int(value)
                                elif key.upper() == "HTTP_VERSION":
                                    value = float(value)
                                elif key.upper() == "INDEX_FILES":
                                    value = value.split()
                                elif key.upper() == "LOGGING":
                                    value = bool(value)
                                elif key.upper() == "PUBLIC_DIR" or key.upper() \
                                        == "CGI_DIR":
                                   value = self._abs_dir(value)
                                self.set(pair[0].upper(), value)
                            except ValueError:
                                raise
                    except ConfigParser.NoSectionError:
                        print("* Wrong or incorrect configuration")
                        print("* Assuming default settings")

        else:
            # Should create a new config file
            print("* Missing configuration file")
            print("* Assuming default settings")

    def _abs_dir(self, value):
        if not os.path.isabs(value):
            value = os.path.join(file_dir, value)
        if not os.path.isdir(value):
            raise NotADirectoryError("Please enter a valid directory name in your config file")
        return value

def test():
    """Creates a config object and prints the default settings"""
    c = Config()
    c.defaults()
    c.print_config()

if __name__ == "__main__":
    test()
