# PHASE 1 BRIDGE -- models/ was never imported, so anything defined there was
# silently never loaded (bsi_shop_setup.py included). Fixed here.
from . import models
from . import controllers
