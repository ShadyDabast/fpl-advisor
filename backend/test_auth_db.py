"""
Tests for auth.py (password hashing, tokens) and db.py (users, squads).

Owner: Member 4, or whoever owns the auth/db layer.

Run with: pytest test_auth_db.py -v
"""

import os
import time
import pytest

from auth import hash_password, verify_password, create_token, verify_token
import db as db_module
from models import Squad, Player

TEST_DB = "test_auth_db.db"


@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    db_module.init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# ---------- password hashing ----------

def test_correct_password_verifies():
    h, salt = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", h, salt) is True


def test_wrong_password_fails():
    h, salt = hash_password("correct-horse-battery-staple")
    assert verify_password("wrong-password", h, salt) is False


def test_same_password_different_salts_gives_different_hashes():
    h1, salt1 = hash_password("samepassword")
    h2, salt2 = hash_password("samepassword")
    assert salt1 != salt2
    assert h1 != h2


# ---------- tokens ----------

def test_token_round_trip():
    token = create_token(user_id=7)
    assert verify_token(token) == 7


def test_tampered_token_rejected():
    token = create_token(user_id=7)
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert verify_token(tampered) is None


def test_malformed_token_rejected():
    assert verify_token("garbage") is None
    assert verify_token("a.b") is None


# ---------- users (db) ----------

def test_create_and_fetch_user():
    h, salt = hash_password("pw123456")
    user_id = db_module.create_user("alice", h, salt, TEST_DB)
    user = db_module.get_user_by_username("alice", TEST_DB)
    assert user["id"] == user_id
    assert user["username"] == "alice"


def test_duplicate_username_rejected():
    h, salt = hash_password("pw123456")
    db_module.create_user("bob", h, salt, TEST_DB)
    with pytest.raises(Exception):
        db_module.create_user("bob", h, salt, TEST_DB)


def test_unknown_username_returns_none():
    assert db_module.get_user_by_username("nobody", TEST_DB) is None


# ---------- squads (db) ----------

def test_squad_save_and_load_for_user():
    h, salt = hash_password("pw123456")
    user_id = db_module.create_user("carol", h, salt, TEST_DB)

    squad = Squad()
    squad.add_player(Player(1, "Haaland", "Man City", "FWD", 14.5, 8.2, 210, 65.3))
    db_module.save_squad_for_user(user_id, squad, TEST_DB)

    loaded = db_module.load_squad_for_user(user_id, TEST_DB)
    assert len(loaded.players) == 1
    assert loaded.players[0].name == "Haaland"


def test_new_user_has_empty_squad():
    h, salt = hash_password("pw123456")
    user_id = db_module.create_user("dave", h, salt, TEST_DB)
    squad = db_module.load_squad_for_user(user_id, TEST_DB)
    assert squad.players == []


def test_squads_are_isolated_between_users():
    h, salt = hash_password("pw123456")
    user1_id = db_module.create_user("erin", h, salt, TEST_DB)
    user2_id = db_module.create_user("frank", h, salt, TEST_DB)

    squad1 = Squad()
    squad1.add_player(Player(1, "Salah", "Liverpool", "MID", 13.0, 7.9, 195, 58.1))
    db_module.save_squad_for_user(user1_id, squad1, TEST_DB)

    squad2 = db_module.load_squad_for_user(user2_id, TEST_DB)
    assert squad2.players == []  # frank's squad unaffected by erin's save
