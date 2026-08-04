#!/usr/bin/env python3
from build_profile import generate_previews, load_profile

if __name__ == "__main__":
    generate_previews(load_profile())
    print("Previews generated successfully.")
