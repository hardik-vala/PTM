import browser_cookie3
import requests
import streamlit as st

def main():
  cj = browser_cookie3.chrome(domain_name="workflowy.com")

  r = requests.get(
      "https://workflowy.com/get_tree_data",
      cookies=cj,
      headers={"Accept": "application/json"},
  )

  workflowy_tree_data = r.json()

  goals = [i["nm"] for i in workflowy_tree_data["items"] if "#Goal" in i["nm"]]

  st.title("Hardik's PTM")
  st.write(goals)

if __name__ == "__main__":
  main()
