# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe import _
from chat.utils import get_full_name


def execute():
    migrate_rooms()
    migrate_messages()


def migrate_rooms():
    """Move pre-2022 rooms onto the current schema.

    Back then participants lived in the `Chat Room User` child table (which
    carried an `is_admin` flag) and `Chat Room` had no `members` field. Frappe
    never drops columns for removed fields, so a site still on the old schema
    keeps `is_admin` after the doctype sync -- its absence means there is
    nothing to migrate.
    """
    if not frappe.db.table_exists('Chat Room'):
        return

    if not frappe.db.has_column('Chat Room User', 'is_admin'):
        return

    old_rooms_list = frappe.qb.from_(
        'Chat Room').select('*').run(as_dict=True)

    for room in old_rooms_list:
        if room.get('members'):
            # already on the current schema
            continue

        room_doc = frappe.get_doc('Chat Room', room['name'])
        room_users = frappe.get_all('Chat Room User', filters={
            'parent': room['name']
        },
            fields=['user', 'is_admin']
        )

        if room['type'] == 'Direct' or room['type'] == 'Group':
            if room['type'] == 'Direct':
                room_doc.room_name = 'Direct Room'
            else:
                room_doc.room_name = room['room_name']
            room_users.append({'user': room['owner'], 'is_admin': 1})
            room_doc.members = ', '.join([item['user'] for item in room_users])
        elif room_users:
            room_doc.type = 'Guest'
            guest_email = room_users[0]['user']
            guest_name = get_full_name(guest_email)

            if not frappe.db.exists('Chat Profile', guest_email):
                guest_doc = frappe.get_doc({
                    'doctype': 'Chat Profile',
                    'email': guest_email,
                    'guest_name': guest_name,
                })
                guest_doc.insert(ignore_mandatory=True)
            room_doc.members = 'Guest'
            room_doc.guest = guest_email
            room_doc.room_name = guest_name
        room_doc.save()


def migrate_messages():
    """Stamp `sender` / `sender_email` on pre-2022 messages.

    Old messages only recorded the `owner`. Messages that already carry a
    `sender_email` have been migrated and are left untouched.
    """
    if not frappe.db.table_exists('Chat Room'):
        return

    old_rooms_list = frappe.qb.from_(
        'Chat Room').select('*').run(as_dict=True)

    for room in old_rooms_list:
        message_list = frappe.db.get_all('Chat Message', filters={
            'room': room['name']
        }, fields=['owner', 'name', 'sender_email'])

        for message_item in message_list:
            if message_item['sender_email']:
                continue

            message_doc = frappe.get_doc('Chat Message', message_item['name'])
            message_doc.sender = 'Guest' if room['type'] == 'Guest' else get_full_name(
                message_item['owner'])

            message_doc.sender_email = message_item['owner']
            message_doc.save()
