# -*- coding: utf-8 -*-

from pynetbox.core.query import RequestError
import re
import unicodedata

class DcimManufacturers(Netbox):
    """
    NetBox DCIM Manufacturer handler for create, update, and delete operations.
    """

    MANAGED_FIELDS = ["name", "slug", "description", "tags"]

    def __init__(self, api, data, check_mode=False):
        """
        Initialize the handler.
        :param api: pynetbox API instance
        :param data: dict containing manufacturer data
        :param check_mode: bool indicating Ansible check mode
        """
        self.api = api
        self.data = data
        self.check_mode = check_mode

        self.set_name()
        self.set_slug()
        self.set_description()
        self.set_tags()
        self.set_id()

        #self.payload = self.build_payload(stage=self.state)
        self.manufacturer = None
        #self.perform_lookup(stage=self.state)

    def set_name(self):
        self.payload['name'] = str(self.data["name"])

    def set_slug(self, from_name=False):
        if "slug" in self.data:
            self.payload['slug'] = str(self.slugify(self.data["slug"]))
        elif from_name:
            self.payload['slug'] = str(self.slugify(self.data["name"]))

    def set_description(self):
        if "description" in self.data:
            self.payload['description'] = str(self.data["description"])

    def set_tags(self):
        if "tags" in self.data:
            self.payload["tags"] = sorted(self._resolve_tags(self.data["tags"]))

    def set_id(self):
        if "id" in self.data:
            self.payload["id"] = int(self.data["id"])

    @property
    def get_payload(self):
        return self.payload


    def build_payload(self, stage="merged"):
        """
        Build the payload to send to the NetBox API based on the input data.

        Args:
            stage (str): The current stage of the operation (e.g., "override", "merged").

        Returns:
            dict: Payload containing manufacturer attributes.
        """
        payload = {
            "name": self.data["name"],
        }

        if "slug" in self.data:
            payload["slug"] = self.slugify(self.data["slug"])

        if stage == "override":
            payload["description"] = self.data.get("description", "")
            payload["tags"] = self._resolve_tags(self.data.get("tags", []))
        elif stage == "merged":
            if "description" in self.data:
                payload["description"] = self.data["description"]
            if "tags" in self.data:
                payload["tags"] = self._resolve_tags(self.data["tags"])

        return payload

    def _resolve_tags(self, tag_names: list) -> list:
        """
        Convert a list of tag names into a list of tag ID dictionaries.

        Args:
            tag_names (list): List of tag names to resolve.

        Returns:
            list: List of dictionaries like {"id": ...} for each tag.
        """
        resolved = []
        for tag in tag_names:
            tag_obj = self.api.extras.tags.get(slug=tag)
            if not tag_obj:
                tag_obj = self.api.extras.tags.get(name=tag)
            if not tag_obj:
                raise Exception("Tag '{}' not found in NetBox.".format(tag))
            resolved.append(tag_obj.id)
        return resolved

    def perform_lookup(self, stage="merged"):
        """
        Try to locate an existing manufacturer using available lookup keys.

        Args:
            stage (str): The current stage ("merged" or "override").
        """
        # On commence par les champs définis explicitement dans `lookup`, s'ils existent
        lookup = self.data.get("lookup", {})

        search_fields = {k: lookup[k] for k in lookup if k in self.MANAGED_FIELDS}

        # Si aucun champ n'est défini dans `lookup`, on regarde dans `data` (priorité : slug > name)
        if not search_fields:
            if "slug" in self.data:
                search_fields["slug"] = self.data["slug"]
            elif "name" in self.data:
                search_fields["name"] = self.data["name"]

        # Si toujours rien, on abandonne
        if not search_fields:
            self.manufacturer = None
            return

        try:
            if "slug" in search_fields:
                self.manufacturer = self.api.dcim.manufacturers.get(slug=search_fields["slug"])
            elif "name" in search_fields:
                results = list(self.api.dcim.manufacturers.filter(name=search_fields["name"]))
                if len(results) == 1:
                    self.manufacturer = results[0]
                elif len(results) > 1:
                    raise Exception("Multiple manufacturers found with name '{}'.".format(search_fields["name"]))
        except Exception as e:
            raise Exception("Lookup failed: {}".format(str(e)))

    @staticmethod
    def slugify(value: str) -> str:
        """
        Simplified slugify function to convert a string into a slug.
        """
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        value = re.sub(r"[^\w\s-]", "", value).strip().lower()
        return re.sub(r"[-\s]+", "-", value)

    def gather_element(self):
        try:
            self.manufacturer = self.api.dcim.manufacturers.get(self.get_payload)

            if not self.manufacturer:
                return {
                    "failed": True,
                    "msg": "No existing manufacturer matches lookup: {}. Aborting creation.".format(self.get_payload)
                }

            return {
                "changed": False,
                "msg": "Manufacturer '{}' has gather.".format(self.manufacturer.name),
                "manufacturer": self.manufacturer.serialize(),
            }
        except RequestError as e:
            return {
                "failed": True,
                "msg": "Failed to gather manufacturer '{}': {}".format(self.get_payload, str(e)),
                "details": getattr(e, "error", str(e)),
            }

    def is_different(self, stage="merged"):
        """
        Compare current and desired state.

        Args:
            stage (str): The current stage of the operation (e.g., "override", "merged").

        :return: dict of changed fields
        """
        if not self.manufacturer:
            return True

        # Construction de l'état actuel du manufacturer
        current = {
            "name": self.manufacturer.name,
            "slug": self.manufacturer.slug,
            "description": self.manufacturer.description,
            "tags": sorted([t["id"] for t in self.manufacturer.tags]),
        }

        # Construction de l'état désiré du manufacturer
        desired = {
            "name": self.payload["name"],
            "slug": self.payload.get("slug", self.manufacturer.slug if self.manufacturer else ""),
            "description": self.payload.get("description", ""),
            "tags": sorted(self.payload.get("tags", [])),
        }

        # Comparer les états actuels et désirés
        changes = {}

        # Vérification des champs dans MANAGED_FIELDS
        for field in self.MANAGED_FIELDS:
            if field not in desired:
                continue
            if desired[field] != current.get(field):
                changes[field] = desired[field]

        # Si on est dans le stage "merged", on évite les suppressions de champs comme "description"
        if stage == "merged":
            # Supprimer uniquement les suppressions implicites (ex: champ absent de self.data)
            if "description" in changes and "description" not in self.data:
                del changes["description"]
            if "tags" in changes and "tags" not in self.data:
                del changes["tags"]

        return changes

    def ensure_present(self):
        """
        Ensure the manufacturer is present and updated if needed.
        :return: dict with operation result
        """

        # Cas : lookup explicite mais aucun résultat
        if self.manufacturer is None and "lookup" in self.data:
            lookup = self.data["lookup"]
            if any(k in lookup for k in ["slug", "name"]):
                return {
                    "failed": True,
                    "msg": "No existing manufacturer matches lookup: {}. Aborting creation.".format(lookup)
                }

        if not self.manufacturer:
            if "slug" not in self.payload:
                self.payload["slug"] = self.slugify(self.payload["name"])

            if self.check_mode:
                return {
                    "changed": True,
                    "msg": "Manufacturer '{}' would be created.".format(self.payload["name"])
                }
            try:
                created = self.api.dcim.manufacturers.create(self.payload)
                return {
                    "changed": True,
                    "msg": "Manufacturer '{}' has been created.".format(created.name),
                    "manufacturer": created.serialize(),
                }
            except RequestError as e:
                return {
                    "failed": True,
                    "msg": "Failed to create manufacturer '{}': {}".format(self.payload.get("name", "unknown"), str(e)),
                    "details": getattr(e, "error", str(e)),
                }


        updates = self.is_different(self.state)
        if updates:
            if self.check_mode:
                return {
                    "changed": True,
                    "msg": "Manufacturer '{}' would be updated.".format(self.manufacturer.name),
                    "updates": updates,
                }
            success = self.manufacturer.update(updates)
            return {
                "changed": True,
                "msg": "Manufacturer '{}' has been updated.".format(self.payload["name"]),
                "updates": updates,
                "manufacturer": self.manufacturer.serialize() if success else {},
            }

        return {
            "changed": False,
            "msg": "No changes required for '{}'.".format(self.manufacturer.name),
            "manufacturer": self.manufacturer.serialize(),
        }

    def override(self):
        """
        Force update with all values, even if no change is detected.
        :return: dict with operation result
        """
        if not self.manufacturer:
            return self.ensure_present()
        if self.check_mode:
            return {
                "changed": True,
                "msg": "Manufacturer '{}' would be overridden.".format(self.payload["name"]),
            }
        success = self.manufacturer.update(self.payload)
        return {
            "changed": True,
            "msg": "Manufacturer '{}' has been overridden.".format(self.payload["name"]),
            "manufacturer": self.manufacturer.serialize() if success else {},
        }

    def ensure_absent(self):
        """
        Ensure the manufacturer is deleted.
        :return: dict with operation result
        """
        if not self.manufacturer:
            return {"changed": False, "msg": "Manufacturer already absent."}
        if self.check_mode:
            return {"changed": True, "msg": "Manufacturer '{}' would be deleted.".format(self.manufacturer.name)}
        self.manufacturer.delete()
        return {"changed": True, "msg": "Manufacturer '{}' has been deleted.".format(self.manufacturer.name)}
