import configparser
import re

from CDserver import pathutils, rights
from CDserver.log import logger


class Rights(rights.BaseRights):
    def __init__(self, configuration):
        super().__init__(configuration)
        self._filename = configuration.get("rights", "file")

    def authorization(self, user, path):
        user = user or ""
        sane_path = pathutils.strip_path(path)
        escaped_user = re.escape(user)
        rights_config = configparser.ConfigParser()
        try:
            if not rights_config.read(self._filename):
                raise RuntimeError("No such file: %r" %
                                   self._filename)
        except Exception as e:
            raise RuntimeError("Failed to load rights file %r: %s" %
                               (self._filename, e)) from e
        for section in rights_config.sections():
            try:
                user_pattern = rights_config.get(section, "user")
                collection_pattern = rights_config.get(section, "collection")
                user_match = re.fullmatch(user_pattern.format(), user)
                collection_match = user_match and re.fullmatch(
                    collection_pattern.format(
                        *map(re.escape, user_match.groups()),
                        user=escaped_user), sane_path)
            except Exception as e:
                raise RuntimeError("Error in section %r of rights file %r: "
                                   "%s" % (section, self._filename, e)) from e
            if user_match and collection_match:
                logger.debug("Rule %r:%r matches %r:%r from section %r",
                             user, sane_path, user_pattern,
                             collection_pattern, section)
                return rights_config.get(section, "permissions")
            logger.debug("Rule %r:%r doesn't match %r:%r from section %r",
                         user, sane_path, user_pattern, collection_pattern,
                         section)
        logger.info("Rights: %r:%r doesn't match any section", user, sane_path)
        return ""
