# Collections & Pooling (GC-Free)

Eliminating garbage collection allocations through pooling.

## Unity Collection Pooling (2021.1+)

Always use `UnityEngine.Pool` for temporary collections in hot paths (Update/FixedUpdate).

### ListPool Example

```csharp
using UnityEngine.Pool;

void ProcessItems()
{
    List<GameObject> tempList;
    using (ListPool<GameObject>.Get(out tempList))
    {
        // Do work
        foreach(var item in mItems) tempList.Add(item);
        Process(tempList);
    } // Auto-released to pool here
}
```

## Object Pooling

For GameObjects or custom objects that are frequently created/destroyed.

```csharp
private ObjectPool<Bullet> mBulletPool;

void Start()
{
    mBulletPool = new ObjectPool<Bullet>(
        createFunc: () => Instantiate(bulletPrefab),
        actionOnGet: b => b.gameObject.SetActive(true),
        actionOnRelease: b => b.gameObject.SetActive(false),
        actionOnDestroy: b => Destroy(b.gameObject)
    );
}
```

## Core Rules

- **MANDATORY**: Never `new List<T>()` in `Update()`. Use `ListPool<T>.Get()`.
- **MANDATORY**: Always release pooled objects (use `using` pattern for collections).
- **AVOID**: Using LINQ (`.ToList()`, `.ToArray()`) in performance-critical code.
