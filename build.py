#!/usr/bin/env python3
"""Uberbespoke static site generator written in python to manage a basic
    portfolio site."""
import csv
import datetime
import json
import os
import shutil
import sys

import jinja2
import mistune


class Utils:
    """Utility tools. Including shorthand for commonly used logic."""

    @staticmethod
    def path(filename: str) -> str:
        """Get abs path to file."""
        return os.path.join(os.getcwd(), filename)

    @staticmethod
    def ifarg(index: int, default: str) -> str:
        """Get cmdline arg safely."""
        return sys.argv[index] if index < len(sys.argv) else default

    @staticmethod
    def infomessage(message: str, flag: bool) -> bool:
        """Show message according to flag, used for verbose mode."""
        if flag:
            print(message)
            return True
        return False

    @staticmethod
    def files(directory_path: str) -> [str]:
        """Get all files from a directory."""
        filepath = lambda filename: os.path.join(directory_path, filename)
        return [filepath(file_) for file_ in os.listdir(directory_path)
                if os.path.isfile(filepath(file_))]

    @staticmethod
    def filename(path: str) -> str:
        """Extract filename from path."""
        return os.path.splitext(os.path.basename(path))[0]

    @staticmethod
    def folder(directory_path: str) -> bool:
        """Safely make directory."""
        if not os.path.isdir(directory_path):
            os.makedirs(directory_path)
            return True
        return False

    @staticmethod
    def ext(filename: str, extension: str) -> str:
        """Append extension to filename."""
        return os.path.extsep.join((filename, extension))


class Config:
    """Configuration information for building site."""
    def __init__(self, config_filename: str):
        self.config_file_loc = Utils.path(config_filename)
        try:
            with open(self.config_file_loc, "r") as f:
                self.user_config = json.load(f)
        except FileNotFoundError:
            Utils.infomessage(
                "No config file, using defaults.",
                self.getconf("verbose_mode"))

    def getconf(self, key: str) -> str:
        """Access configuration data by key."""
        return self.user_config.get(key, Config.default_config[key])

    default_filename = "config.json"
    default_config = {
        "data_dir": "data",
        "template_dir": "templates",
        "posts_dir": "posts",
        "public_dir": "public",
        "data_indexs": [],
        "create_public_dir": True,
        "data_format": "csv",
        "verbose_mode": False,
        "home_template": "home.html",
        "date_format": "%d%m%y"
    }


class Collector:
    """Collector base class. Used to implement data collectors."""
    def __init__(self, directory_name: str):
        self.data_dir_name = directory_name
        self.data_dir = Utils.path(self.data_dir_name)

        self.datafiles: [{str: any}] = []

    def extract_data(self) -> None:
        """Parse files from data dir. Should be overwritten by children."""
        return None

    def getdatafile(self, name) -> {str: any}:
        """Get data stored in datafiles array."""
        for file_ in self.datafiles:
            if file_["filename"] == name:
                return file_["data"]
        return []
    
    @staticmethod
    def apply_headings(headings: [str], array_: [[str]]) -> [{str: str}]:
        """Utility function to apply headings to csv data."""
        _new_array: [{str: str}] = []
        for object_ in array_:
            _new_object: {str: str} = {}
            for i, field in enumerate(object_):
                _new_object[headings[i]] = field
            _new_array.append(_new_object)
        return _new_array


class DataCollector(Collector):
    """Collector child. Parse csv data."""
    def __init__(self, data_directory: str):
        Collector.__init__(self, data_directory)
        self.extract_data()

    def extract_data(self) -> [{str: str or [{str: str}]}]:
        """Parse files from data dir. Overwrite parent method."""
        for file_ in Utils.files(self.data_dir):
            with open(file_, "r") as f:
                csvreader = csv.reader(f, delimiter=",")
                headings = next(csvreader)
                self.datafiles.append({
                    "filename": Utils.filename(file_),
                    "data": Collector.apply_headings(
                        headings,
                        list(csvreader)[::-1])})

    def parse_categories(self, file_: str) -> {str: str or [{str: str}]}:
        """Sort list of date entries into categories."""
        datafile = self.getdatafile(file_)
        categories: [str] = []
        for entry in datafile:  # Get list of categories
            if entry["category"] not in categories:
                categories.append(entry["category"])

        sorted_data: [{str: str or [{str: str}]}] = []
        for category in categories:  # Sort data into categories
            new_entry: {str: str or [{str: str}]} = {"name": category}
            new_entry["entries"] = list(filter(
                lambda x: x["category"] == category, datafile))
            sorted_data.append(new_entry)

        return sorted_data


class PostCollector(Collector):

    def __init__(self, data_directory: str, date_format: str):
        Collector.__init__(self, data_directory)
        
        self.date_format = date_format
        self.markdown_inst = mistune.Markdown()
        self.extract_data()
        self.datafiles = self.parse_date()

    def extract_data(self) -> [{str: str}]:
        for file_ in Utils.files(self.data_dir):
            with open(file_, "r") as f:
                json_, markdown = f.read().split("}")
            json_ = json.loads(json_ + "}")
            html = self.markdown_inst(markdown)
            datafile = {
                "filename": Utils.ext(Utils.filename(file_), "html"),
                "data": html }
            for key, value in json_.items():
                datafile[key] = value
            self.datafiles.append(datafile)
        return self.datafiles

    def parse_categories(self) -> {str: [{str: str}]}:
        """Sort list of data entries into categories."""
        categories: [str] = []
        for entry in self.datafiles:
            if entry["category"] not in categories:
                categories.append(entry["category"])

        sorted_data: [{str: str}] = []
        for category in categories:
            new_entry: {str: str} = {"name": category.capitalize()}
            new_entry["entries"] = list(filter(
                lambda x: x["category"] == category, self.datafiles))
            sorted_data.append(new_entry)

        return sorted_data

    def parse_date(self) -> [{str: str}]:
        """Sort list of data entries by date."""
        datafiles = self.datafiles
        for datafile in datafiles:
            datafile["datetime"] = datetime.datetime.strptime(
                datafile["date"], self.date_format)

        return sorted(datafiles, key=lambda x: x["datetime"], reverse=True)


class TemplateCollector(Collector):
    """Collector child. Parse template files."""
    def __init__(self, data_directory: str):
        Collector.__init__(self, data_directory)
        self.extract_data()

    def extract_data(self) -> [{str: str or [{str: str}]}]:
        """Parse files from data dir. Overwrite parent method."""
        for file_ in Utils.files(self.data_dir):
            with open(file_, "r") as f:
                self.datafiles.append({
                    "filename": Utils.filename(file_),
                    "data": f.read()})


class TemplateUtils:
    """Utility functions for templates."""

    @staticmethod
    def abbrev(string: str, maxlength: int = 60) -> str:
        """Truncate string."""
        if len(string) < maxlength:
            return string
        truncated = string[:maxlength - 2]
        if truncated.endswith(" "):
            truncated = truncated[:-1]
        return truncated + ".."

    @staticmethod
    def len_(string: str) -> int:
        """Get length of string."""
        return len(string)


class Master(Config):
    """Main class, handles all file creation. Recieves data from collectors."""
    def __init__(self):
        super().__init__(Utils.ifarg(1, Config.default_filename))
        self.data_handle = DataCollector(self.getconf("data_dir"))
        self.template_handle = TemplateCollector(self.getconf("template_dir"))
        self.post_handle = PostCollector(
                self.getconf("posts_dir"),
                self.getconf("date_format"))

        self.build_dir = Utils.path("build")
        self.public_dir = os.path.join(self.build_dir, "static")
        self.posts_dir = os.path.join(self.build_dir, "posts")
    
    def build(self) -> None:
        """Build static site."""
        # Create build dir
        Utils.folder(self.build_dir)

        # Create public folder
        _public_dir = Utils.path(self.getconf("public_dir"))
        Utils.folder(self.public_dir)

        # Migrate public files
        for file_ in Utils.files(_public_dir):
            _fileloc = os.path.join(self.public_dir, os.path.basename(file_))
            shutil.copyfile(file_, _fileloc)

        # Create data index files
        for file_ in self.getconf("data_indexs"):
            data = self.data_handle.parse_categories(file_)
            template = jinja2.Template(self.template_handle.getdatafile(file_))
            name = file_.capitalize()
            html = template.render(name=name, data=data, utils=TemplateUtils)
            newfile = os.path.join(self.build_dir, Utils.ext(file_, "html"))
            with open(newfile, "w") as f:
                f.write(html)

        # Create post index
        Utils.folder(self.posts_dir)
        posts = self.post_handle.parse_categories()
        template = jinja2.Template(self.template_handle.getdatafile("dir"))
        name = "Writings"
        html = template.render(
            name=name,
            data=posts,
            utils=TemplateUtils,
            dir_="posts")
        newfile = os.path.join(self.posts_dir, Utils.ext("index", "html"))
        with open(newfile, "w") as f:
            f.write(html)

        # Create posts
        template = jinja2.Template(self.template_handle.getdatafile("essay"))
        for post in self.post_handle.datafiles:
            html = template.render(post=post, utils=TemplateUtils)
            newfile = os.path.join(self.posts_dir, post["filename"])
            with open(newfile, "w") as f:
                f.write(html)

        # Create index html file
        index_template = jinja2.Template(self.template_handle.getdatafile(
            Utils.filename(self.getconf("home_template"))))
        dataobj = {file_["filename"]: file_["data"] for file_ in
            self.data_handle.datafiles}
        html = index_template.render(
                data=dataobj,
                utils=TemplateUtils,
                posts=self.post_handle.datafiles)
        index_location = os.path.join(self.build_dir, Utils.ext(
            "index", "html"))
        with open(index_location, "w") as f:
            f.write(html)


if __name__ == "__main__":
    Master().build()
