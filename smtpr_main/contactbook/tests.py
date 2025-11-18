from django.test import TestCase

# Create your tests here.
import json
from django.test import TestCase, Client
from django.urls import reverse
from .models import Contact, Label


class ContactAPITestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_contact_create_success(self):
        payload = {
            "name": "Rutger",
            "email": "rutger@smart.pr",
            "phone": "112",
        }
        response = self.client.post(
            "/contactbook/contact/create",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["name"], "Rutger")
        self.assertEqual(data["email"], "rutger@smart.pr")
        self.assertEqual(data["phone"], "112")

        self.assertEqual(Contact.objects.count(), 1)

    def test_contact_create_missing_fields(self):
        payload = {
            "name": "Rutger Without Phone",
            "email": "rutger@smart.pr",
        }
        response = self.client.post(
            "/contactbook/contact/create",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)  # Bad Request

    def test_label_create_and_list(self):
        resp1 = self.client.post(
            "/contactbook/label/create",
            data=json.dumps({"name": "friends"}),
            content_type="application/json",
        )
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertTrue(data1["created"])
        self.assertEqual(data1["name"], "friends")

        resp2 = self.client.post(
            "/contactbook/label/create",
            data=json.dumps({"name": "friends"}),
            content_type="application/json",
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertFalse(data2["created"])  # should not create on the second time

        # and there shall only be one in the database
        resp_list = self.client.get("/contactbook/label/list")
        self.assertEqual(resp_list.status_code, 200)
        labels = resp_list.json()
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]["name"], "friends")

        resp3 = self.client.post(
            "/contactbook/label/create",
            data=json.dumps({"name": "vampires"}),
            content_type="application/json",
        )

        # and there shall be two in the database
        resp_list = self.client.get("/contactbook/label/list")
        self.assertEqual(resp_list.status_code, 200)
        labels = resp_list.json()
        self.assertEqual(len(labels), 2)
        self.assertEqual(labels[0]["name"], "friends")
        self.assertEqual(labels[1]["name"], "vampires")


    def test_add_and_remove_labels_from_contact(self):
        resp = self.client.post(
            "/contactbook/label/create",
            data=json.dumps({"name": "friends"}),
            content_type="application/json",
        )
        resp = self.client.post(
            "/contactbook/label/create",
            data=json.dumps({"name": "favorites"}),
            content_type="application/json",
        )

        # create contact
        tmp_contact = Contact.objects.create(
            name="Hiro", email="Hiro@smart.pr", phone="113"
        )

        # add_label
        payload_add = {
            "contact_id": tmp_contact.id,
            "labels": ["friends", "favorites"],
        }
        resp_add = self.client.post(
            "/contactbook/contact/add_label",
            data=json.dumps(payload_add),
            content_type="application/json",
        )
        self.assertEqual(resp_add.status_code, 200)
        data_add = resp_add.json()
        self.assertEqual(data_add["contact_id"], tmp_contact.id)
        self.assertCountEqual(data_add["labels"], ["friends", "favorites"])

        tmp_contact.refresh_from_db()
        self.assertEqual(tmp_contact.labels.count(), 2)

        # remove_label
        payload_remove = {
            "contact_id": tmp_contact.id,
            "labels": ["friends"],
        }
        resp_remove = self.client.post(
            "/contactbook/contact/remove_label",
            data=json.dumps(payload_remove),
            content_type="application/json",
        )
        self.assertEqual(resp_remove.status_code, 200)
        data_remove = resp_remove.json()
        self.assertEqual(data_remove["contact_id"], tmp_contact.id)
        self.assertEqual(data_remove["labels"], ["favorites"])

        tmp_contact.refresh_from_db()
        self.assertEqual(tmp_contact.labels.count(), 1)
        self.assertEqual(tmp_contact.labels.first().name, "favorites")

    def test_contact_list_basic_and_filter_by_labels(self):
        # data init
        lbl_friends = Label.objects.create(name="lbl_friends")
        lbl_work = Label.objects.create(name="lbl_work")
        lbl_bff = Label.objects.create(name="lbl_bff")

        c1 = Contact.objects.create(
            name="Boss smart pr", email="a1@smart.pr", phone="111"
        )
        c2 = Contact.objects.create(
            name="Nice reporter", email="a2@nu.nl", phone="222"
        )
        c3 = Contact.objects.create(
            name="Bol boss", email="a3@bol.com", phone="333"
        )

        c4 = Contact.objects.create(
            name="Bol lil boss", email="a4@bol.com", phone="444"
        )

        c1.labels.add(lbl_friends) # Boss smart pr is now our friend
        c2.labels.add(lbl_work) # reporter is for work
        c2.labels.add(lbl_bff) # reporter is also bff
        c3.labels.add(lbl_friends, lbl_work) # BOL boss is both friend and work

        # return all 3 when not filtering by labels
        resp_all = self.client.get("/contactbook/contact/list")
        self.assertEqual(resp_all.status_code, 200)
        data_all = resp_all.json()
        self.assertEqual(len(data_all), 4)

        # filter by one label: labels=lbl_friends
        resp_friends = self.client.get("/contactbook/contact/list?labels=lbl_friends")
        self.assertEqual(resp_friends.status_code, 200)
        data_friends = resp_friends.json()
        # c1 & c3
        ids = {c["id"] for c in data_friends}
        self.assertSetEqual(ids, {c1.id, c3.id})

        # filter by mult label：?labels=lbl_friends,lbl_work
        resp_multi = self.client.get("/contactbook/contact/list?labels=lbl_friends,lbl_work")
        self.assertEqual(resp_multi.status_code, 200)
        data_multi = resp_multi.json()
        self.assertEqual(len(data_multi), 3)

        # filter by mult label but with OR mode
        resp_multi = self.client.get("/contactbook/contact/list?labels=lbl_bff,lbl_work,lbl_friends&match=or")
        self.assertEqual(resp_multi.status_code, 200)
        data_multi = resp_multi.json()
        # should be c2, c1 and c3
        self.assertEqual(len(data_multi), 3)

        # filter by mult label but with AND mode
        resp_multi = self.client.get("/contactbook/contact/list?labels=lbl_bff,lbl_work&match=and")
        self.assertEqual(resp_multi.status_code, 200)
        data_multi = resp_multi.json()
        # should return 1, c2
        self.assertEqual(len(data_multi), 1)

        # filter by mult label but with AND mode
        resp_multi = self.client.get("/contactbook/contact/list?labels=lbl_bff,lbl_friends,lbl_work&match=and")
        self.assertEqual(resp_multi.status_code, 200)
        data_multi = resp_multi.json()
        # should return 0
        self.assertEqual(len(data_multi), 0)

    def test_contact_list_emails_only(self):
        label = Label.objects.create(name="friends")
        c1 = Contact.objects.create(
            name="Boss smart pr", email="a1@smart.pr", phone="111"
        )
        c2 = Contact.objects.create(
            name="Nice reporter", email="a2@nu.nl", phone="222"
        )
        c3 = Contact.objects.create(
            name="Bol boss", email="a3@bol.com", phone="333"
        )
        c1.labels.add(label)
        c2.labels.add(label)

        resp = self.client.get("/contactbook/contact/list?labels=friends&emails_only=1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("emails", data)
        self.assertCountEqual(
            data["emails"],
            ["a1@smart.pr", "a2@nu.nl"],
        )


    def test_contact_delete(self):
        a_contact = Contact.objects.create(
            name="Boss smart pr", email="a1@smart.pr", phone="111"
        )
        self.assertEqual(Contact.objects.count(), 1)

        resp = self.client.get(f"/contactbook/contact/del?id={a_contact.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["deleted_id"], str(a_contact.id))

        self.assertEqual(Contact.objects.count(), 0)

    def test_label_delete(self):
        a_label = Label.objects.create(name="temp")
        self.assertEqual(Label.objects.count(), 1)

        resp = self.client.get(f"/contactbook/label/del?id={a_label.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["deleted_id"], str(a_label.id))

        self.assertEqual(Label.objects.count(), 0)
