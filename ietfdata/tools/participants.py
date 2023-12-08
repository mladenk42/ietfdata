# Copyright (C) 2023 University of Glasgow
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import json
import sys

from datetime    import timedelta
from dataclasses import dataclass, field
from typing      import List, Dict, Optional, Iterator

from ietfdata.datatracker     import *
from ietfdata.datatracker_ext import *
from ietfdata.mailarchive2    import *

class Participant:
    person_id   : Optional[str]
    identifiers : Dict[str,List[str]]


    def __init__(self, person_id: Optional[str] = None):
        self.person_id   = person_id
        self.identifiers = {}
        print(f"Participant({id(self)}) created ({self.person_id})")


    def add_identifier(self, ident_type:str, ident_value:str):
        if ident_type not in self.identifiers:
            self.identifiers[ident_type] = [ident_value]
            print(f"Participant({id(self)}) add_identifier: {ident_type} -> {ident_value}")
        else:
            if ident_value not in self.identifiers[ident_type]:
                self.identifiers[ident_type].append(ident_value)
                print(f"Participant({id(self)}) add_identifier: {ident_type} -> {ident_value}")
            else:
                print(f"Participant({id(self)}) has_identifier: {ident_type} -> {ident_value}")


    def num_idents(self) -> int:
        count = 0
        for ident_type in self.identifiers:
            count += len(self.identifiers[ident_type])
        return count


    def merge_into(self, other):
        print(f"Participant({id(self)}) merge data into Participant({id(other)})")
        for ident_type in self.identifiers:
            for ident_value in self.identifiers[ident_type]:
                other.add_identifier(ident_type, ident_value)
        self.identifiers = {}


    def __repr__(self) -> str:
        return f"Participant({id(self)}){str(self.identifiers)}"



class ParticipantDB:
    pid: int
    idents: Dict[str,Dict[str,Participant]]
    people: set[Participant]

    def __init__(self, path:Optional[Path] = None):
        self.pid = 0
        self.idents = {}
        self.people = set()
        if path is not None:
            with open(path, "r") as inf:
                saved_data = json.load(inf)
                for pid in saved_data:
                    person = Participant(pid)
                    self.people.add(person)
                    for ident_type in saved_data[pid]:
                        for ident_value in saved_data[pid][ident_type]:
                            person.add_identifier(ident_type, ident_value)
                            if not ident_type in self.idents:
                                self.idents[ident_type] = {}
                            self.idents[ident_type][ident_value] = person
                    pid_int = int(pid[4:])
                    if pid_int > self.pid:
                        self.pid = pid_int


    def save(self, path:Path):
        people = {}
        for person in self.people:
            if person.person_id is None:
                self.pid += 1
                person.person_id = f"PID:{self.pid:06}"
            people[person.person_id] = person.identifiers
        with open(path, "w") as outf:
            json.dump(people, outf, indent=3, sort_keys=True)


    def person_with_identifier(self, ident_type: str, ident_value: str) -> Participant:
        """
        Specify that there is a person identified by the specific identifer.

        Example: `pdb.person_with_identifier("email", "j.doe@example.org")
        """
        person = None
        if not ident_type in self.idents:
            person = Participant()
            person.add_identifier(ident_type, ident_value)
            self.people.add(person)
            self.idents[ident_type] = {}
            self.idents[ident_type][ident_value] = person
        else:
            if ident_value not in self.idents[ident_type]:
                person = Participant()
                person.add_identifier(ident_type, ident_value)
                self.people.add(person)
                self.idents[ident_type][ident_value] = person
            else:
                person = self.idents[ident_type][ident_value]
                print(f"Participant({id(person)}) already_exists: {ident_type} -> {ident_value}")
        return person


    def identifies_same_person(self, ident_type1:str, ident_value1: str, ident_type2:str, ident_value2: str):
        """
        Specify that the two identifiers refer to the same person.

        Example: `pdb.identifies_same_person("email", "j.doe@example.org", "name", "Jane Doe")
        """
        if not ident_type1 in self.idents:
            self.idents[ident_type1] = {}
        if not ident_type2 in self.idents:
            self.idents[ident_type2] = {}

        if   ident_value1 not in self.idents[ident_type1] and ident_value2 not in self.idents[ident_type2]:
            # Neither identifier represents a known person
            self.person_with_identifier(ident_type1, ident_value1)
            self.identifies_same_person(ident_type1, ident_value1, ident_type2, ident_value2)
        elif ident_value1     in self.idents[ident_type1] and ident_value2 not in self.idents[ident_type2]:
            # There is a person associated with the first identifier but not the second
            person = self.idents[ident_type1][ident_value1]
            person.add_identifier(ident_type2, ident_value2)
            self.idents[ident_type2][ident_value2] = person
        elif ident_value1 not in self.idents[ident_type1] and ident_value2     in self.idents[ident_type2]:
            # There is a person associated with the second identifier but not the first
            person = self.idents[ident_type2][ident_value2]
            person.add_identifier(ident_type1, ident_value1)
            self.idents[ident_type1][ident_value1] = person
        elif ident_value1     in self.idents[ident_type1] and ident_value2     in self.idents[ident_type2]:
            # Both identifiers are associated with people
            person1 = self.idents[ident_type1][ident_value1]
            person2 = self.idents[ident_type2][ident_value2]
            if person1 == person2:
                # Both identifiers are associated with the same person, nothing to do
                pass
            else:
                # Both identifiers exist but refer to different people that
                # must be merged into one.
                # If one person has a person_id assigned but the other does
                # not, merge the identifiers for the person that does not have
                # a person_id into the record for the person that does.
                if   person1.person_id is     None and person2.person_id is     None:
                    person2.merge_into(person1)
                    self._update_refs(person2, person1)
                    self.people.remove(person2)
                elif person1.person_id is not None and person2.person_id is     None:
                    person2.merge_into(person1)
                    self._update_refs(person2, person1)
                    self.people.remove(person2)
                elif person1.person_id is     None and person2.person_id is not None:
                    person1.merge_into(person2)
                    self._update_refs(person1, person2)
                    self.people.remove(person1)
                elif person1.person_id is not None and person2.person_id is not None:
                    # If both people have a person_id, merge the records and leave
                    # behind a "replaced_by" field to indicate that the merge took
                    # place.
                    if person2.num_idents() > person1.num_idents():
                        person2.merge_into(person1)
                        self._update_refs(person2, person1)
                        person2.add_identifier("replaced_by", person1.person_id)
                    else:
                        person1.merge_into(person2)
                        self._update_refs(person1, person2)
                        person1.add_identifier("replaced_by", person2.person_id)
                else:
                    raise RuntimeError("This cannot happen (1)")
        else:
            raise RuntimeError("This cannot happen (2)")


    def _update_refs(self, from_person: Participant, to_person: Participant):
        """
        Private helper method: do not use.
        """
        print(f"Participant({id(from_person)}) -> Participant({id(to_person)})")
        for ident_type in self.idents:
            for ident_value in self.idents[ident_type]:
                if self.idents[ident_type][ident_value] == from_person:
                    self.idents[ident_type][ident_value] = to_person
                    print(f"    {ident_type} -> {ident_value}")



if __name__ == "__main__":
    if len(sys.argv) == 2:
        old_path = None
        new_path = Path(sys.argv[1])
    elif len(sys.argv) == 3:
        old_path = Path(sys.argv[1])
        new_path = Path(sys.argv[2])
    else:
        print("Usage: python3 -m ietfdata.tools.participants [new.json]")
        print("   or: python3 -m ietfdata.tools.participants [old.json] [new.json]")
        sys.exit(1)

    print(f"*** ietfdata.tools.participants")
    if old_path is not None:
        print(f"Loading: {old_path}")

    if old_path == new_path:
        print("")
        print("ERROR: refusing to overwrite input file")
        sys.exit(2)

    pdb = ParticipantDB(old_path)

    # Add identifiers based on the IETF DataTracker:
    dt  = DataTrackerExt(cache_timeout = timedelta(hours=1))
    for msg in dt.emails():
        pdb.person_with_identifier("email", msg.address)
        pdb.identifies_same_person("email", msg.address, "dt_person_uri", str(msg.person))
        if msg.person is not None:
            person = dt.person(msg.person)
            if person is not None:
                print(person)
                if person.name is not None and person.name != "":
                    pdb.identifies_same_person("dt_person_uri", str(msg.person), "name", person.name)
                if person.name_from_draft is not None and person.name_from_draft != "":
                    pdb.identifies_same_person("dt_person_uri", str(msg.person), "name", person.name_from_draft)
                if person.ascii is not None and person.ascii != "":
                    pdb.identifies_same_person("dt_person_uri", str(msg.person), "name", person.ascii)
                if person.ascii_short is not None and person.ascii_short != "":
                    pdb.identifies_same_person("dt_person_uri", str(msg.person), "name", person.ascii_short)


    for resource in dt.person_ext_resources():
        if str(resource.name) == "/api/v1/name/extresourcename/webpage/":
            pdb.identifies_same_person("dt_person_uri", str(resource.person), "webpage", resource.value)
        if str(resource.name) == "/api/v1/name/extresourcename/github_username/":
            pdb.identifies_same_person("dt_person_uri", str(resource.person), "github_username", resource.value)
        if str(resource.name) == "/api/v1/name/extresourcename/gitlab_username/":
            pdb.identifies_same_person("dt_person_uri", str(resource.person), "gitlab_username", resource.value)


    # Add identifiers based on the IETF mailing list archive:
    cache = {}
    ma = MailArchive()
    for n in ma.mailing_list_names():
        ml = ma.mailing_list(n)
        for envelope in ml.messages():
            message = envelope.contents()
            for addr in message["from"].addresses:
                email_addr = f"{addr.username}@{addr.domain}"
                name  = addr.display_name
                pdb.person_with_identifier("email", email_addr)

                key = f"{name} <{email_addr}>"
                if key in cache:
                    person = cache[key]
                    print(f"cache hit: {key}")
                else:
                    person = dt.person_from_name_email(name, email_addr)
                    cache[key] = person
                if person is not None:
                    pdb.identifies_same_person("email", email_addr, "dt_person_uri", str(person.resource_uri))

    print(f"Saving: {new_path}")
    pdb.save(new_path)


