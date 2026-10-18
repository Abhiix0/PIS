import tseslint from "typescript-eslint";
import hooks from "eslint-plugin-react-hooks";

export default tseslint.config(...tseslint.configs.recommended, hooks.configs.flat.recommended);
