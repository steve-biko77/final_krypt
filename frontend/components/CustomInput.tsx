import { FormControl, FormField, FormLabel, FormMessage } from './ui/form'
import { Input } from './ui/input'

import { Control, FieldPath } from 'react-hook-form'
import { z } from 'zod'
import { authFormSchema } from '@/lib/utils'

type FormSchema = ReturnType<typeof authFormSchema>

interface CustomInput {
  control: Control<z.infer<FormSchema>>,
  name: FieldPath<z.infer<FormSchema>>,
  label: string,
  placeholder: string
}

// Optimisation mobile-first — type/inputMode corrects par champ pour que le
// clavier natif adapté s'affiche directement (email, numérique téléphone).
const FIELD_INPUT_PROPS: Partial<Record<string, { type: string; inputMode?: 'email' | 'tel' }>> = {
  email: { type: 'email', inputMode: 'email' },
  phone: { type: 'tel', inputMode: 'tel' },
  password: { type: 'password' },
}

const CustomInput = ({ control, name, label, placeholder }: CustomInput) => {
  const { type, inputMode } = FIELD_INPUT_PROPS[name] ?? { type: 'text' }

  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <div className="form-item">
          <FormLabel className="form-label">
            {label}
          </FormLabel>
          <div className="flex w-full flex-col">
            <FormControl>
              <Input
                placeholder={placeholder}
                // h-11 (44px) : taille tactile minimale mobile (refonte
                // frontend partie 2/4, point 5) — input-class ne fixe pas de
                // hauteur, on l'ajoute explicitement ici.
                className="input-class h-11"
                type={type}
                inputMode={inputMode}
                {...field}
              />
            </FormControl>
            <FormMessage className="form-message mt-2" />
          </div>
        </div>
      )}
    />
  )
}

export default CustomInput