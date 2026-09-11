from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import AuditEvent, BOM, BOMItem, BOMRevision, Part, PartRevision, Unit


class BOMStructureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user('bom_engineer')
        self.user.groups.add(Group.objects.get_or_create(name='plm:engineer')[0])
        self.client.force_authenticate(self.user)
        self.unit = Unit.objects.create(code='PCS', name='件', dimension='count')
        part = Part.objects.create(part_code='9801-00101')
        self.child = PartRevision.objects.create(part=part, name='Child', unit=self.unit, revision_state='released')
        self.bom = BOM.objects.create(bom_code='BOM-900001')
        self.revision = BOMRevision.objects.create(bom=self.bom, root_part_revision=self.child)
        self.url = f'/api/v1/bom-revisions/{self.revision.pk}/items/'

    def payload(self, **changes):
        return {'line_no': 1, 'child_part_revision': str(self.child.pk), 'quantity': '2.000000',
                'unit': self.unit.pk, 'position': 'R1', **changes}

    def post(self, **changes):
        self.revision.refresh_from_db()
        return self.client.post(self.url, self.payload(**changes), format='json', HTTP_IF_MATCH=str(self.revision.row_version))

    def test_canonical_crud_tree_and_etag(self):
        created = self.post()
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created['ETag'], '"2"')
        child = self.post(line_no=2, parent_item=created.data['id'], position='R2')
        self.assertEqual(child.status_code, 201, child.data)
        tree = self.client.get(f'/api/v1/bom-revisions/{self.revision.pk}/tree/')
        self.assertEqual(tree.status_code, 200, tree.data)
        self.assertEqual(tree.data['node_count'], 2)
        self.assertEqual(tree.data['tree'][0]['children'][0]['id'], child.data['id'])
        detail = f"{self.url}{created.data['id']}/"
        before = AuditEvent.objects.count()
        stale = self.client.patch(detail, {'quantity': '3'}, format='json', HTTP_IF_MATCH='1')
        self.assertEqual(stale.status_code, 412)
        self.assertEqual(AuditEvent.objects.count(), before)
        self.assertEqual(self.client.delete(detail, HTTP_IF_MATCH='3').status_code, 409)

    def test_position_uniqueness_is_per_parent_and_invalid_quantity_is_atomic(self):
        first = self.post()
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(self.post(line_no=2).status_code, 409)
        self.assertEqual(self.post(line_no=2, parent_item=first.data['id']).status_code, 201)
        before = BOMItem.objects.count()
        self.assertEqual(self.post(line_no=3, position='R3', quantity='0').status_code, 422)
        self.assertEqual(BOMItem.objects.count(), before)

    def test_cross_revision_parent_cycle_and_unit_dimension(self):
        first = self.post()
        second = self.post(line_no=2, position='R2', parent_item=first.data['id'])
        other = BOMRevision.objects.create(bom=self.bom, revision='B', root_part_revision=self.child)
        foreign = BOMItem.objects.create(bom_revision=other, child_part_revision=self.child, quantity=1, line_no=1)
        bad = self.post(line_no=3, position='R3', parent_item=str(foreign.pk))
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(bad.data['code'], 'PARENT_ITEM_CROSS_BOM')
        cycle = self.client.patch(f"{self.url}{first.data['id']}/", {'parent_item': second.data['id']}, format='json', HTTP_IF_MATCH='3')
        self.assertEqual(cycle.status_code, 422)
        self.assertEqual(cycle.data['code'], 'BOM_CYCLE_DETECTED')
        mass = Unit.objects.create(code='KG', name='千克', dimension='mass')
        invalid = self.post(line_no=3, position='R3', unit=mass.pk)
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.data['code'], 'UNIT_DIMENSION_MISMATCH')

    def test_no_position_requires_reason(self):
        missing = self.post(position='__NO_POSITION__')
        self.assertEqual(missing.status_code, 400)
        self.assertIn('no_position_reason', missing.data)
        valid = self.post(position='__NO_POSITION__', no_position_reason='functional component')
        self.assertEqual(valid.status_code, 201, valid.data)

    def test_released_revision_and_unreleased_child_are_rejected(self):
        self.child.revision_state = 'draft'; self.child.save(update_fields=['revision_state'])
        invalid = self.post()
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.data['code'], 'REFERENCED_REVISION_NOT_RELEASED')
        self.revision.revision_state = 'released'; self.revision.save(update_fields=['revision_state'])
        self.assertEqual(self.post().status_code, 409)

    def test_depth_budget_does_not_write_the_sixteenth_level(self):
        parent = None
        for level in range(1, 16):
            response = self.post(line_no=level, position=f'R{level}', parent_item=parent)
            self.assertEqual(response.status_code, 201, response.data)
            parent = response.data['id']
        response = self.post(line_no=16, position='R16', parent_item=parent)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data['code'], 'BOM_TREE_BUDGET_EXCEEDED')
        self.assertEqual(BOMItem.objects.count(), 15)
