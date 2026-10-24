from pathlib import Path
import os
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.runtime'/'python'))
sys.path.insert(0,str(ROOT))
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
if __name__=='__main__':
    import pytest
    (ROOT/'tmp').mkdir(exist_ok=True)  # git-ignored; absent in a fresh clone, pytest --basetemp needs its parent
    raise SystemExit(pytest.main([str(ROOT/'tests'),'-q','--basetemp',str(ROOT/'tmp'/'pytest-run')]))
