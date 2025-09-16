def f():
    words=""
    text = "ceci\n est un\n texte"
for _ in range(10):  # Boucle inutile : répète le même traitement 10 fois
        for line in text.split("\n"):
            for word in line.split(" "):

                words+=word
    for _ in range(100): 
        print("texte")            
    return words
f()         
 