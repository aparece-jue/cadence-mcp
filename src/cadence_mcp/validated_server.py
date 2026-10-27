"""Default supported release entry point, separate from the expanded development server."""
from .server import create_server,parse_config

def main():create_server(parse_config(),profile='validated').run(transport='stdio')
if __name__=='__main__':main()
