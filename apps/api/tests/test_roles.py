import pytest
from fastapi import HTTPException
from app.auth import Principal, require_owner, require_write_access


def test_require_owner_allows_owner():
    p = Principal(user_id="u1", company_id="c1", role="owner")
    assert require_owner(p) == p


def test_require_owner_blocks_staff():
    p = Principal(user_id="u1", company_id="c1", role="staff")
    with pytest.raises(HTTPException) as exc_info:
        require_owner(p)
    assert exc_info.value.status_code == 403


def test_require_write_access_allows_staff_and_owner():
    owner = Principal(user_id="u1", company_id="c1", role="owner")
    staff = Principal(user_id="u2", company_id="c1", role="staff")
    assert require_write_access(owner) == owner
    assert require_write_access(staff) == staff


def test_require_write_access_blocks_read_only():
    read_only = Principal(user_id="u3", company_id="c1", role="solo-lectura")
    with pytest.raises(HTTPException) as exc_info:
        require_write_access(read_only)
    assert exc_info.value.status_code == 403
