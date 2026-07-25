using UnityEngine;
using UnityEditor;

// Adds a mesh collider to each game object that contains collider in its name
public class BUImporter : AssetPostprocessor
{
  void OnPostprocessModel(GameObject obj)
  {
    Apply(obj.transform);
  }

  void Apply(Transform obj)
  {
    if (obj.name.ToLower().Contains("collider"))
      obj.gameObject.AddComponent<MeshCollider>();

    foreach (Transform child in obj)
    {
      if (child.name.ToLower().Contains("collider"))
        child.GetComponent<MeshRenderer>().enabled = false;
      Apply(child);
    }
  }
}