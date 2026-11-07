"""Keep historical research validation separate from current formal admission."""
import subprocess
import sys
from priority_market_archive import main
if sys.argv[1:] == ['validate']:
    main()
else:
    subprocess.run([sys.executable, 'scripts/evidence/priority_markets.py', *sys.argv[1:]], check=True)
