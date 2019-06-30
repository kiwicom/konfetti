from .core import Konfig
from .environ import EnvVariable
from .laziness import LazyVariable
from .vault import *

# Public API
env = EnvVariable.env
vault = VaultVariable.vault
vault_file = VaultVariable.vault_file
lazy = LazyVariable.lazy
