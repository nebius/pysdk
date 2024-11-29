class Abc:
    pass


if __name__ == "__main__":
    abc = Abc()
    setattr(abc, "#attr", 5)
    print(abc)
