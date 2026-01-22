import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useSetupWizard } from '@/hooks/use-setup-wizard';
import { motion } from 'framer-motion';
import { ArrowLeft, ArrowRight, Info, MapPin } from 'lucide-react';

const discos = [
  { 
    code: 'LESCO', 
    name: 'Lahore Electric Supply Company',
    region: 'Lahore, Kasur, Sheikhupura, Okara',
    rate: '24.20'
  },
  { 
    code: 'K-Electric', 
    name: 'K-Electric',
    region: 'Karachi',
    rate: '26.50'
  },
  { 
    code: 'MEPCO', 
    name: 'Multan Electric Power Company',
    region: 'Multan, Sahiwal, Bahawalpur, DG Khan',
    rate: '23.80'
  },
  { 
    code: 'IESCO', 
    name: 'Islamabad Electric Supply Company',
    region: 'Islamabad, Rawalpindi, Attock',
    rate: '24.00'
  },
  { 
    code: 'PESCO', 
    name: 'Peshawar Electric Supply Company',
    region: 'Peshawar, Mardan, Swat',
    rate: '23.50'
  },
  { 
    code: 'FESCO', 
    name: 'Faisalabad Electric Supply Company',
    region: 'Faisalabad, Jhang, Sargodha',
    rate: '23.90'
  },
  { 
    code: 'HESCO', 
    name: 'Hyderabad Electric Supply Company',
    region: 'Hyderabad, Mirpurkhas',
    rate: '24.10'
  },
  { 
    code: 'QESCO', 
    name: 'Quetta Electric Supply Company',
    region: 'Quetta, Balochistan',
    rate: '22.80'
  },
  { 
    code: 'GEPCO', 
    name: 'Gujranwala Electric Power Company',
    region: 'Gujranwala, Sialkot, Gujrat',
    rate: '24.30'
  },
  { 
    code: 'SEPCO', 
    name: 'Sukkur Electric Power Company',
    region: 'Sukkur, Larkana',
    rate: '23.60'
  },
];

const TariffStep = () => {
  const { nextStep, prevStep, data, updateData } = useSetupWizard();
  
  const selectedDisco = discos.find(d => d.code === data.disco);
  const isValid = data.disco.trim().length > 0;

  // Auto-suggest based on city
  const suggestedDisco = discos.find(d => 
    d.region.toLowerCase().includes(data.city.toLowerCase())
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <div className="text-center space-y-2">
        <h2 className="text-xl font-bold">Select Your Electricity Provider</h2>
        <p className="text-sm text-muted-foreground">
          This helps us calculate your savings accurately.
        </p>
      </div>

      {suggestedDisco && !data.disco && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-primary/10 rounded-lg p-3 flex items-center gap-3"
        >
          <MapPin className="h-5 w-5 text-primary shrink-0" />
          <div className="flex-1">
            <p className="text-sm">
              Based on your location ({data.city}), we suggest:
            </p>
            <p className="font-medium">{suggestedDisco.name}</p>
          </div>
          <Button 
            size="sm" 
            variant="secondary"
            onClick={() => updateData({ disco: suggestedDisco.code })}
          >
            Select
          </Button>
        </motion.div>
      )}

      <div className="space-y-2">
        <Label htmlFor="disco">Distribution Company (DISCO)</Label>
        <Select value={data.disco} onValueChange={(value) => updateData({ disco: value })}>
          <SelectTrigger>
            <SelectValue placeholder="Select your electricity provider" />
          </SelectTrigger>
          <SelectContent>
            {discos.map((disco) => (
              <SelectItem key={disco.code} value={disco.code}>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{disco.code}</span>
                  <span className="text-muted-foreground">- {disco.name}</span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {selectedDisco && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="bg-muted/50 rounded-lg p-4 space-y-3"
        >
          <div className="flex items-start gap-3">
            <Info className="h-5 w-5 text-primary shrink-0 mt-0.5" />
            <div className="space-y-2">
              <div>
                <p className="font-medium">{selectedDisco.name}</p>
                <p className="text-sm text-muted-foreground">{selectedDisco.region}</p>
              </div>
              <div className="grid grid-cols-2 gap-4 pt-2 border-t">
                <div>
                  <p className="text-xs text-muted-foreground">Base Rate</p>
                  <p className="text-lg font-semibold">Rs. {selectedDisco.rate}/kWh</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Net Metering</p>
                  <p className="text-sm font-medium text-green-600 dark:text-green-400">Available</p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      <p className="text-xs text-muted-foreground text-center">
        You can customize detailed tariff settings later in Billing Settings.
      </p>

      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={prevStep}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Button onClick={nextStep} disabled={!isValid}>
          Continue
          <ArrowRight className="h-4 w-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
};

export default TariffStep;
