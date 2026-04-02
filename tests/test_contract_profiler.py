"""Tests for the contract profiler."""
from __future__ import annotations

import pytest

from app.core.analyzer.contract_profiler import profile_contract


BASIC_CONTRACT = """
pragma solidity ^0.8.0;
contract Foo {
    function bar() public {}
}
"""

OWNABLE_CONTRACT = """
pragma solidity ^0.8.0;
import "@openzeppelin/contracts/access/Ownable.sol";
contract MyToken is Ownable {
    function privileged() external onlyOwner {}
}
"""

MINTABLE_CONTRACT = """
pragma solidity ^0.8.0;
contract MintToken {
    function mint(address to, uint256 amount) public {
        _mint(to, amount);
    }
}
"""

PROXY_CONTRACT = """
pragma solidity ^0.8.0;
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
contract MyProxy is ERC1967Proxy {
    fallback() external payable {
        address impl = _implementation();
        assembly { delegatecall(gas(), impl, 0, calldatasize(), 0, 0) }
    }
}
"""

SELFDESTRUCT_CONTRACT = """
pragma solidity ^0.8.0;
contract Killable {
    function kill() public {
        selfdestruct(payable(msg.sender));
    }
}
"""


class TestContractProfiler:
    def test_basic_contract_has_no_flags(self):
        profile = profile_contract(BASIC_CONTRACT)
        assert profile.is_proxy is False
        assert profile.has_mint is False
        assert profile.has_ownership is False
        assert profile.has_selfdestruct is False

    def test_ownable_detected(self):
        profile = profile_contract(OWNABLE_CONTRACT)
        assert profile.has_ownership is True

    def test_mint_detected(self):
        profile = profile_contract(MINTABLE_CONTRACT)
        assert profile.has_mint is True

    def test_proxy_detected(self):
        profile = profile_contract(PROXY_CONTRACT)
        assert profile.is_proxy is True

    def test_selfdestruct_detected(self):
        profile = profile_contract(SELFDESTRUCT_CONTRACT)
        assert profile.has_selfdestruct is True

    def test_pragma_extracted(self):
        profile = profile_contract(BASIC_CONTRACT)
        assert len(profile.compiler_pragmas) == 1
        assert "0.8.0" in profile.compiler_pragmas[0]
