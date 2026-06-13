"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Button } from "./ui/button";

const PaymentTransferForm = (_props: PaymentTransferFormProps) => {
  const [isLoading] = useState(false);

  return (
    <div className="flex flex-col gap-4 p-6">
      <p className="text-16 text-gray-600">
        Le module de transfert Mobile Money sera disponible prochainement.
      </p>
      <Button disabled={isLoading} className="payment-transfer_btn w-fit">
        {isLoading ? (
          <>
            <Loader2 size={20} className="animate-spin" /> &nbsp; Envoi...
          </>
        ) : (
          "Envoyer des fonds"
        )}
      </Button>
    </div>
  );
};

export default PaymentTransferForm;
