/**
 * @name Hardcoded cryptographic key
 * @description A hardcoded byte string is used as a cryptographic key,
 *              allowing any attacker who reads the source to decrypt protected data.
 * @kind problem
 * @problem.severity error
 * @id python/hardcoded-vault-key
 * @tags security
 *       external/cwe/cwe-321
 */

import python

from Call base64Call, StringValue hardcoded
where
  base64Call.getFunc().(Attribute).getName() = "b64encode" and
  base64Call.getFunc().(Attribute).getObject().(Attribute).getName() in
    ["urlsafe_b64encode", "b64encode"] and
  hardcoded = base64Call.getArg(0).(Bytes).getS() and
  // Only flag where the literal is inside a method (not a test)
  exists(Function f | base64Call.getEnclosingFunction() = f)
select base64Call,
  "Hardcoded bytes literal used as cryptographic key: '" + hardcoded + "' (CWE-321)"
