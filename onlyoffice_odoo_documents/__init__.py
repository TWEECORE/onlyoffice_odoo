# Copyright (C) 2026 Ascensio System SIA

from . import controllers
from . import models


def _link_existing_files(env):
    env["onlyoffice.file"]._link_existing_files_to_documents()
