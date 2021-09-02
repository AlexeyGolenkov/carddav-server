import os

EXAMPLES_FOLDER = os.path.join(os.path.dirname(__file__), "static")


def get_file_path(file_name):
    return os.path.join(EXAMPLES_FOLDER, file_name)


def get_file_content(file_name):
    with open(get_file_path(file_name), encoding="utf-8") as fd:
        return fd.read()


def configuration_to_dict(configuration):
    return {section: {option: configuration.get_raw(section, option)
                      for option in configuration.options(section)
                      if not option.startswith("_")}
            for section in configuration.sections()
            if not section.startswith("_")}
