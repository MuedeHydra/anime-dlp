# -------------------------------------------
#   config reader
# -------------------------------------------

def datatype(value: str):
    try:
        return int(value)
    except ValueError:
        pass
    value = value.removeprefix('"').removesuffix('"')
    value = value.removeprefix("'").removesuffix("'")
    return value


def formater(value: str):
    if value.startswith("["):
        li_formated = []
        value = value.removeprefix("[").removesuffix("]")
        li = value.split(",")
        for i in range(len(li)):
            li[i] = li[i].strip(" ")
            li_formated.append(datatype(li[i]))
        return li_formated
    return datatype(value)


def conf_reader(file: str) -> dict:
    di = {}
    with open(file, "r") as conf:
        for i in conf:
            if i == "\n":
                continue
            if i.startswith("#"):
                continue
            li = i.split("=")
            di[li[0].rstrip(" ")] = formater(li[1].strip(" ").removesuffix("\n"))

    return di


# x = conf_reader("anime-dlp.conf")
# print(x)
