using UnityEngine;
using UnityEditor;
using System.IO;
using System;
using System.Linq;

public class BUImporter : AssetPostprocessor
{

  private Material newMaterial;

  void OnPostprocessGameObjectWithUserProperties(GameObject obj, string[] propNames, object[] values)
  {
    for (int i = 0; i < propNames.Length; i++)
    {
      if (propNames[i] == "shader_type")
      {
        string shaderType = values[i].ToString();
        if (shaderType == "STANDARD")
        {
          CreateStandardShader(obj);
        }
        else if (shaderType == "SPECULAR")
        {
          CreateSpecularShader(obj);
        }
        else if (shaderType == "AUTODESK")
        {
          CreateAutodeskInteractiveShader(obj);
        }
        else if (shaderType == "HDRP_LIT")
        {
          CreateHDRPShader(obj);
        }
        else
        {
          CreateStandardShader(obj);
        }
      }
    }
  }

  void OnPostprocessModel(GameObject obj)
  {

    // Store the name of the object
    string objName = obj.name;
    if (objName.Contains("_LOD"))
    {
      // Split the name into parts using '_LOD' as the separator
      string[] parts = objName.Split(new string[] { "_LOD" }, StringSplitOptions.None);

      // Use the first part of the name (before '_LOD')
      objName = parts[0];
    }

    // Apply collider component to the model
    ApplyCollider(obj.transform);

    // Apply the new material to the model and its children
    // ApplyMaterial(obj.transform, newMaterial);

    // Delay the creation of the asset until after the import process has finished
    EditorApplication.delayCall += () =>
    {
      // Use the stored object name
      string materialDirectory = Path.Combine("Assets/Materials", objName);

      // Check if the directory exists, if not, create it
      if (!Directory.Exists(materialDirectory))
      {
        Directory.CreateDirectory(materialDirectory);
      }

      // Save the material to a file
      AssetDatabase.CreateAsset(newMaterial, Path.Combine(materialDirectory, objName + ".mat"));

      // Refresh the AssetDatabase to make sure the new material appears in the editor
      AssetDatabase.Refresh();
    };

  }

  void ApplyCollider(Transform obj)
  {
    if (obj.name.ToLower().Contains("collider"))
      obj.gameObject.AddComponent<MeshCollider>();

    foreach (Transform child in obj)
    {
      if (child.name.ToLower().Contains("collider"))
      {
        child.GetComponent<MeshRenderer>().enabled = false;
        ApplyCollider(child);
      }
      else
      {
        ApplyCollider(child);
      }
    }
  }

  void ApplyMaterial(Transform obj, Material newMaterial)
  {
    // Set the material for the MeshRenderer component if it exists
    MeshRenderer meshRenderer = obj.GetComponent<MeshRenderer>();
    if (meshRenderer != null)
    {
      meshRenderer.material = newMaterial;
    }

    foreach (Transform child in obj)
    {
      if (child.name.ToLower().Contains("LOD"))
      {
        ApplyMaterial(child, newMaterial);
      }
      else
      {
        ApplyMaterial(child, newMaterial);
      }
    }
  }

  void CreateStandardShader(GameObject obj)
  {

    // Store the name of the object
    string objName = obj.name;
    if (objName.Contains("_LOD"))
    {
      // Split the name into parts using '_LOD' as the separator
      string[] parts = objName.Split(new string[] { "_LOD" }, StringSplitOptions.None);

      // Use the first part of the name (before '_LOD')
      objName = parts[0];
    }

    // Create a new material
    newMaterial = new Material(Shader.Find("Standard"));
    Debug.Log($"Material created: {newMaterial.name}");

    // Load all textures from the model's folder in the 'textures' folder
    // string[] textureFiles = Directory.GetFiles(Path.Combine("Assets/Textures", objName), "*.png");
    string[] textureFiles = Directory.GetFiles("Assets/Textures", "*.png", SearchOption.AllDirectories);
    textureFiles = textureFiles.Where(file => Path.GetFileNameWithoutExtension(file).Contains(objName)).ToArray();

    foreach (string textureFile in textureFiles)
    {
      // Get the filename without the extension
      string textureName = Path.GetFileNameWithoutExtension(textureFile);

      // Load the texture
      Texture2D texture = AssetDatabase.LoadAssetAtPath<Texture2D>(textureFile);

      // Split the texture name into parts
      string[] parts = textureName.Split('_');

      // Check if the texture's name contains the object's name
      if (parts.Length > 2 && parts[0] == objName)
      {
        // Get the type of the texture
        string type = parts[2];

        // Assign the texture to the corresponding slot in the material
        if (type == "Albedo")
        {
          newMaterial.SetTexture("_MainTex", texture);
          Debug.Log("Texture assigned: Albedo");
        }
        else if (type == "Metallic")
        {
          newMaterial.SetTexture("_MetallicGlossMap", texture);
          Debug.Log("Texture assigned: Metallic");
        }
        else if (type == "Normal" || type == "NormalGL")
        {
          newMaterial.SetTexture("_BumpMap", texture);
          Debug.Log("Texture assigned: Normal");
        }
        else if (type == "Height")
        {
          newMaterial.SetTexture("_ParallaxMap", texture);
          Debug.Log("Texture assigned: Height");
        }
        else if (type == "Occlusion")
        {
          newMaterial.SetTexture("_OcclusionMap", texture);
          Debug.Log("Texture assigned: Occlusion");
        }
        else if (type == "Emission")
        {
          newMaterial.EnableKeyword("_EMISSION");
          newMaterial.globalIlluminationFlags = MaterialGlobalIlluminationFlags.BakedEmissive;
          newMaterial.SetTexture("_EmissionMap", texture);
          Debug.Log("Texture assigned: Emission");
        }
      }
    }
  }

  void CreateSpecularShader(GameObject obj)
  {

    // Store the name of the object
    string objName = obj.name;
    if (objName.Contains("_LOD"))
    {
      // Split the name into parts using '_LOD' as the separator
      string[] parts = objName.Split(new string[] { "_LOD" }, StringSplitOptions.None);

      // Use the first part of the name (before '_LOD')
      objName = parts[0];
    }

    // Find the shader
    newMaterial = new Material(Shader.Find("Standard (Specular setup)"));
    Debug.Log($"Material created: {newMaterial.name}");

    // Load all textures from the model's folder in the 'textures' folder
    // string[] textureFiles = Directory.GetFiles(Path.Combine("Assets/Textures", objName), "*.png");
    string[] textureFiles = Directory.GetFiles("Assets/Textures", "*.png", SearchOption.AllDirectories);
    textureFiles = textureFiles.Where(file => Path.GetFileNameWithoutExtension(file).Contains(objName)).ToArray();

    foreach (string textureFile in textureFiles)
    {
      // Get the filename without the extension
      string textureName = Path.GetFileNameWithoutExtension(textureFile);

      // Load the texture
      Texture2D texture = AssetDatabase.LoadAssetAtPath<Texture2D>(textureFile);


      // Split the texture name into parts
      string[] parts = textureName.Split('_');

      // Check if the texture's name contains the object's name
      if (parts.Length > 2 && parts[0] == objName)
      {
        // Get the type of the texture
        string type = parts[2];

        // Assign the texture to the corresponding slot in the material
        if (type == "Albedo")
        {
          newMaterial.SetTexture("_MainTex", texture);
          Debug.Log("Texture assigned: Albedo");
        }
        else if (type == "Specular")
        {
          newMaterial.SetTexture("_SpecGlossMap", texture);
          Debug.Log("Texture assigned: Specular");
        }
        else if (type == "Normal" || type == "NormalGL")
        {
          newMaterial.SetTexture("_BumpMap", texture);
          Debug.Log("Texture assigned: Normal");
        }
        else if (type == "Height")
        {
          newMaterial.SetTexture("_ParallaxMap", texture);
          Debug.Log("Texture assigned: Height");
        }
        else if (type == "Occlusion")
        {
          newMaterial.SetTexture("_OcclusionMap", texture);
          Debug.Log("Texture assigned: Occlusion");
        }
        else if (type == "Emission")
        {
          newMaterial.EnableKeyword("_EMISSION");
          newMaterial.globalIlluminationFlags = MaterialGlobalIlluminationFlags.BakedEmissive;
          newMaterial.SetTexture("_EmissionMap", texture);
          Debug.Log("Texture assigned: Emission");
        }
      }
    }
  }

  void CreateAutodeskInteractiveShader(GameObject obj)
  {

    // Store the name of the object
    string objName = obj.name;
    if (objName.Contains("_LOD"))
    {
      // Split the name into parts using '_LOD' as the separator
      string[] parts = objName.Split(new string[] { "_LOD" }, StringSplitOptions.None);

      // Use the first part of the name (before '_LOD')
      objName = parts[0];
    }

    // Create a new material
    newMaterial = new Material(Shader.Find("Autodesk Interactive"));
    Debug.Log($"Material created: {newMaterial.name}");

    // Load all textures from the model's folder in the 'textures' folder
    // string[] textureFiles = Directory.GetFiles(Path.Combine("Assets/Textures", objName), "*.png");
    string[] textureFiles = Directory.GetFiles("Assets/Textures", "*.png", SearchOption.AllDirectories);
    textureFiles = textureFiles.Where(file => Path.GetFileNameWithoutExtension(file).Contains(objName)).ToArray();

    foreach (string textureFile in textureFiles)
    {
      // Get the filename without the extension
      string textureName = Path.GetFileNameWithoutExtension(textureFile);

      // Load the texture
      Texture2D texture = AssetDatabase.LoadAssetAtPath<Texture2D>(textureFile);

      // Split the texture name into parts
      string[] parts = textureName.Split('_');

      // Check if the texture's name contains the object's name
      if (parts.Length > 2 && parts[0] == objName)
      {
        // Get the type of the texture
        string type = parts[2];

        // Assign the texture to the corresponding slot in the material
        if (type == "Albedo")
        {
          newMaterial.SetTexture("_MainTex", texture);
          Debug.Log("Texture assigned: Albedo");
        }
        else if (type == "Metallic")
        {
          newMaterial.SetTexture("_MetallicGlossMap", texture);
          Debug.Log("Texture assigned: Metallic");
        }
        else if (type == "Roughness")
        {
          newMaterial.SetTexture("_SpecGlossMap", texture);
          Debug.Log("Texture assigned: Roughness");
        }
        else if (type == "Normal" || type == "NormalGL")
        {
          newMaterial.SetTexture("_BumpMap", texture);
          Debug.Log("Texture assigned: Normal");
        }
        else if (type == "Height")
        {
          newMaterial.SetTexture("_ParallaxMap", texture);
          Debug.Log("Texture assigned: Height");
        }
        else if (type == "Occlusion")
        {
          newMaterial.SetTexture("_OcclusionMap", texture);
          Debug.Log("Texture assigned: Occlusion");
        }
        else if (type == "Emission")
        {
          newMaterial.EnableKeyword("_EMISSION");
          newMaterial.globalIlluminationFlags = MaterialGlobalIlluminationFlags.BakedEmissive;
          newMaterial.SetTexture("_EmissionMap", texture);
          Debug.Log("Texture assigned: Emission");
        }
      }
    }
  }

  void CreateHDRPShader(GameObject obj)
  {

    // Store the name of the object
    string objName = obj.name;
    if (objName.Contains("_LOD"))
    {
      // Split the name into parts using '_LOD' as the separator
      string[] parts = objName.Split(new string[] { "_LOD" }, StringSplitOptions.None);

      // Use the first part of the name (before '_LOD')
      objName = parts[0];
    }

    // Create a new material
    newMaterial = new Material(Shader.Find("HDRP/Lit"));
    Debug.Log($"Material created: {newMaterial.name}");

    // Load all textures from the model's folder in the 'textures' folder
    // string[] textureFiles = Directory.GetFiles(Path.Combine("Assets/Textures", objName), "*.png");
    string[] textureFiles = Directory.GetFiles("Assets/Textures", "*.png", SearchOption.AllDirectories);
    textureFiles = textureFiles.Where(file => Path.GetFileNameWithoutExtension(file).Contains(objName)).ToArray();

    foreach (string textureFile in textureFiles)
    {
      // Get the filename without the extension
      string textureName = Path.GetFileNameWithoutExtension(textureFile);

      // Load the texture
      Texture2D texture = AssetDatabase.LoadAssetAtPath<Texture2D>(textureFile);

      // Split the texture name into parts
      string[] parts = textureName.Split('_');

      // Check if the texture's name contains the object's name
      if (parts.Length > 2 && parts[0] == objName)
      {
        // Get the type of the texture
        string type = parts[2];

        // Assign the texture to the corresponding slot in the material
        if (type == "Base")
        {
          newMaterial.SetTexture("_BaseColorMap", texture);
          Debug.Log("Texture assigned: Base");
        }
        else if (type == "Mask")
        {
          newMaterial.SetTexture("_MaskMap", texture);
          Debug.Log("Texture assigned: Mask");
        }
        else if (type == "Normal" || type == "NormalGL")
        {
          newMaterial.SetTexture("_NormalMap", texture);
          Debug.Log("Texture assigned: Normal");
        }
        else if (type == "Bent Normal")
        {
          newMaterial.SetTexture("_BentNormalMap", texture);
          Debug.Log("Texture assigned: Bent Normal");
        }
        else if (type == "Coat")
        {
          newMaterial.SetTexture("_CoatMaskMap", texture);
          Debug.Log("Texture assigned: Coat");
        }
        else if (type == "Detail")
        {
          newMaterial.SetTexture("_DetailMap", texture);
          Debug.Log("Texture assigned: Detail");
        }
        else if (type == "Emission")
        {
          newMaterial.EnableKeyword("_UseEmissiveIntensity");
          newMaterial.globalIlluminationFlags = MaterialGlobalIlluminationFlags.BakedEmissive;
          newMaterial.SetTexture("_EmissiveColorMap", texture);
          Debug.Log("Texture assigned: Emission");
        }
      }
    }
  }
}