"""Exercises the future server guard with a minimal Frappe contract fixture."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

class Denied(Exception):
    pass

def deny(message, error):
    raise error(message)

frappe = SimpleNamespace(session=SimpleNamespace(user='manager'), PermissionError=Denied,
    throw=deny, get_roles=lambda user: ['System Manager'], get_cached_value=lambda *a: 1,
    has_permission=lambda *a, **k: True, db=SimpleNamespace(get_value=lambda *a: 'Manager'),
    whitelist=lambda: lambda fn: fn)
sys.modules['frappe'] = frappe
spec = importlib.util.spec_from_file_location('guard', Path(__file__).parents[1] / 'integration/erpnext/management_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

class GuardTests(unittest.TestCase):
    def setUp(self):
        frappe.session.user = 'manager'
        frappe.get_roles = lambda user: ['System Manager']
        frappe.get_cached_value = lambda *a: 1
        frappe.has_permission = lambda *a, **k: True
    def test_guest_is_denied(self):
        frappe.session.user = 'Guest'
        with self.assertRaises(Denied): guard.get_management_context()
    def test_ordinary_role_is_denied(self):
        frappe.get_roles = lambda user: ['Customer']
        with self.assertRaises(Denied): guard.get_management_context()
    def test_disabled_user_is_denied(self):
        frappe.get_cached_value = lambda *a: 0
        with self.assertRaises(Denied): guard.get_management_context()
    def test_document_permissions_still_apply(self):
        frappe.has_permission = lambda *a, **k: False
        with self.assertRaises(Denied): guard.require_system_manager('Item', 'write')
    def test_exact_session_identity_and_document_permission_are_used(self):
        args=[]
        frappe.has_permission=lambda *a, **k: args.append((a,k)) or True
        self.assertEqual(guard.require_system_manager('Item','write',{'name':'A'}),'manager')
        self.assertEqual(args[0][1], {'ptype':'write','doc':{'name':'A'},'user':'manager'})
    def test_context_is_read_only_and_cannot_accept_claimed_identity(self):
        self.assertEqual(guard.get_management_context()['roles'], ['System Manager'])
        with self.assertRaises(TypeError): guard.get_management_context(user='admin')
    def test_revoked_role_is_checked_on_each_operation(self):
        guard.require_system_manager()
        frappe.get_roles=lambda user: []
        with self.assertRaises(Denied): guard.require_system_manager('Item','read')

if __name__ == '__main__': unittest.main()
